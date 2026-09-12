"""
gateway.py
==========
El agente (DASHIA u otro) NUNCA llama a client.py directamente. Llama a
TradingGateway.execute_signal(), que aplica los límites duros descritos
en blueprint_arquitectura_seguridad.md §4 — independientes de lo que el
agente "quiera" hacer:

  - símbolo dentro de la whitelist
  - tamaño máximo de posición
  - circuit breaker de pérdida diaria máxima
  - límite de órdenes por minuto
  - registro de auditoría inmutable (append-only) de cada decisión

Esto es lo que separa "un agente con un bug" de "un agente con un bug
que además puede vaciar la cuenta".
"""

from __future__ import annotations
import json
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import GatewayLimits
from .client import BinanceConnector

try:
    from dashia_engine.risk import RiskConfig, position_size, sl_tp_levels
except ImportError:  # permite correr este paquete de forma aislada si hace falta
    RiskConfig = None
    def position_size(equity, price, cfg):
        return (equity * 0.1) / price
    def sl_tp_levels(entry_price, is_long, cfg, atr_value):
        return (None, None)

log = logging.getLogger("trading_gateway")


class GatewayRejection(RuntimeError):
    """Una orden fue bloqueada por el gateway — esto es un éxito de seguridad, no un bug."""


class CircuitBreakerTripped(RuntimeError):
    """Se alcanzó la pérdida diaria máxima permitida — el agente queda pausado."""


@dataclass
class _DailyState:
    day: str
    pnl_usd: float = 0.0
    order_timestamps: list = field(default_factory=list)
    tripped: bool = False


class TradingGateway:
    def __init__(self, connector: BinanceConnector, limits: GatewayLimits,
                 risk_cfg=None, audit_log_path: str = "audit_log.jsonl"):
        self.connector = connector
        self.limits = limits
        self.risk_cfg = risk_cfg
        self.audit_path = Path(audit_log_path)
        self._state = _DailyState(day=self._today())

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _roll_day_if_needed(self):
        today = self._today()
        if self._state.day != today:
            log.info("Nuevo día UTC — reseteo de pérdida diaria y circuit breaker")
            self._state = _DailyState(day=today)

    def _audit(self, event: dict):
        event["ts"] = datetime.now(timezone.utc).isoformat()
        with self.audit_path.open("a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Checks duros
    # ------------------------------------------------------------------
    def _check_symbol(self, symbol: str):
        if symbol not in self.limits.allowed_symbols:
            raise GatewayRejection(f"Símbolo {symbol} no está en la whitelist del gateway")

    def _check_rate_limit(self):
        now = time.time()
        window = [t for t in self._state.order_timestamps if now - t < 60]
        self._state.order_timestamps = window
        if len(window) >= self.limits.max_orders_per_minute:
            raise GatewayRejection(
                f"Límite de {self.limits.max_orders_per_minute} órdenes/min alcanzado"
            )

    def _check_circuit_breaker(self):
        self._roll_day_if_needed()
        if self._state.tripped:
            raise CircuitBreakerTripped("Circuit breaker activo: pérdida diaria máxima alcanzada")
        if self._state.pnl_usd <= -abs(self.limits.max_daily_loss_usd):
            self._state.tripped = True
            self._audit({"event": "circuit_breaker_tripped", "daily_pnl_usd": self._state.pnl_usd})
            raise CircuitBreakerTripped("Circuit breaker activo: pérdida diaria máxima alcanzada")

    def _check_position_size(self, notional_usd: float):
        if notional_usd > self.limits.max_position_usd:
            raise GatewayRejection(
                f"Tamaño de posición ${notional_usd:.2f} excede el máximo "
                f"permitido de ${self.limits.max_position_usd:.2f}"
            )

    # ------------------------------------------------------------------
    def record_fill_pnl(self, pnl_usd: float):
        """Llamar cuando una posición se cierra, para alimentar el circuit breaker."""
        self._roll_day_if_needed()
        self._state.pnl_usd += pnl_usd
        self._audit({"event": "fill_pnl", "pnl_usd": pnl_usd, "daily_pnl_usd": self._state.pnl_usd})

    def execute_signal(self, agent_id: str, action: str, symbol: str,
                        equity_usd: float, price_hint: Optional[float] = None,
                        atr_value: Optional[float] = None) -> dict:
        """
        action: "open_long" | "open_short" | "close_long" | "close_short"
        Único punto de entrada que un agente debe usar. Nunca llama a
        self.connector directamente desde fuera de esta clase.
        """
        self._roll_day_if_needed()
        self._check_circuit_breaker()
        self._check_symbol(symbol)
        self._check_rate_limit()

        price = price_hint or self.connector.get_last_price(symbol)

        if action in ("close_long", "close_short"):
            side = "sell" if action == "close_long" else "buy"
            result = self.connector.place_market_order(symbol, side, self._last_qty(symbol))
            self._audit({"event": "order", "agent_id": agent_id, "action": action,
                         "symbol": symbol, "price": price, "result_id": result.get("id")})
            self._state.order_timestamps.append(time.time())
            return result

        is_long = action == "open_long"
        qty = position_size(equity_usd, price, self.risk_cfg) if self.risk_cfg else (equity_usd * 0.02) / price
        notional = qty * price
        self._check_position_size(notional)

        side = "buy" if is_long else "sell"
        result = self.connector.place_market_order(symbol, side, qty)
        self._last_qty_cache = {symbol: qty}

        sl, tp = sl_tp_levels(price, is_long, self.risk_cfg, atr_value) if self.risk_cfg else (None, None)
        if sl:
            self.connector.place_stop_loss(symbol, "sell" if is_long else "buy", qty, sl)
        if tp:
            self.connector.place_take_profit(symbol, "sell" if is_long else "buy", qty, tp)

        self._state.order_timestamps.append(time.time())
        self._audit({
            "event": "order", "agent_id": agent_id, "action": action, "symbol": symbol,
            "qty": qty, "price": price, "sl": sl, "tp": tp, "result_id": result.get("id"),
        })
        return result

    def _last_qty(self, symbol: str) -> float:
        return getattr(self, "_last_qty_cache", {}).get(symbol, 0.0)
