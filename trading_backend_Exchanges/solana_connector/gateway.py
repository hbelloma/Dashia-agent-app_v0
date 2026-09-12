"""
gateway.py
==========
Mismo rol que binance_connector.gateway.TradingGateway: el agente nunca
llama a JupiterClient/TradingWallet/SolanaRPC directo, todo pasa por acá.

Diferencia importante de este lado (documentada también en el README):
Jupiter agrega SWAPS SPOT. No hay "short" aquí — vender SOL por USDC no
es lo mismo que un short apalancado. Para shorts reales en Solana se
necesitaría integrar un protocolo de perps (p. ej. Drift), que queda
fuera de este conector.
"""

from __future__ import annotations
import base64
import json
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import SolanaGatewayLimits, SolanaSettings, WELL_KNOWN_MINTS
from .jupiter_client import JupiterClient
from .wallet import TradingWallet
from .rpc import SolanaRPC

try:
    from dashia_engine.risk import RiskConfig, position_size
except ImportError:
    RiskConfig = None
    def position_size(equity, price, cfg):
        return (equity * 0.1) / price

log = logging.getLogger("solana_gateway")

USDC_DECIMALS = 6


class GatewayRejection(RuntimeError):
    pass


class CircuitBreakerTripped(RuntimeError):
    pass


@dataclass
class _DailyState:
    day: str
    pnl_usd: float = 0.0
    order_timestamps: list = field(default_factory=list)
    tripped: bool = False


class SolanaTradingGateway:
    def __init__(self, jupiter: JupiterClient, wallet: TradingWallet, rpc: SolanaRPC,
                 limits: SolanaGatewayLimits, risk_cfg=None,
                 audit_log_path: str = "solana_audit_log.jsonl"):
        self.jupiter = jupiter
        self.wallet = wallet
        self.rpc = rpc
        self.limits = limits
        self.risk_cfg = risk_cfg
        self.audit_path = Path(audit_log_path)
        self._state = _DailyState(day=self._today())
        self._positions: dict[str, float] = {}  # símbolo -> unidades del token en tenencia (tracking simple)

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _roll_day_if_needed(self):
        today = self._today()
        if self._state.day != today:
            self._state = _DailyState(day=today)

    def _audit(self, event: dict):
        event["ts"] = datetime.now(timezone.utc).isoformat()
        with self.audit_path.open("a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    def _check_symbol(self, symbol: str):
        if symbol not in self.limits.allowed_symbols:
            raise GatewayRejection(f"Símbolo {symbol} no está en la whitelist del gateway")

    def _check_rate_limit(self):
        now = time.time()
        window = [t for t in self._state.order_timestamps if now - t < 60]
        self._state.order_timestamps = window
        if len(window) >= self.limits.max_orders_per_minute:
            raise GatewayRejection(f"Límite de {self.limits.max_orders_per_minute} órdenes/min alcanzado")

    def _check_circuit_breaker(self):
        self._roll_day_if_needed()
        if self._state.tripped:
            raise CircuitBreakerTripped("Circuit breaker activo: pérdida diaria máxima alcanzada")
        if self._state.pnl_usd <= -abs(self.limits.max_daily_loss_usd):
            self._state.tripped = True
            self._audit({"event": "circuit_breaker_tripped", "daily_pnl_usd": self._state.pnl_usd})
            raise CircuitBreakerTripped("Circuit breaker activo: pérdida diaria máxima alcanzada")

    def _check_quote_slippage(self, quote: dict):
        impact = float(quote.get("priceImpactPct", 0) or 0) * 100
        if impact > (self.limits.max_slippage_bps / 100):
            raise GatewayRejection(f"Impacto de precio {impact:.2f}% excede el máximo permitido")

    def record_fill_pnl(self, pnl_usd: float):
        self._roll_day_if_needed()
        self._state.pnl_usd += pnl_usd
        self._audit({"event": "fill_pnl", "pnl_usd": pnl_usd, "daily_pnl_usd": self._state.pnl_usd})

    # ------------------------------------------------------------------
    def execute_signal(self, agent_id: str, action: str, symbol: str, equity_usd: float) -> dict:
        """
        action: "open_long" (comprar `symbol` con USDC) | "close_long" (vender de vuelta a USDC)
        """
        self._roll_day_if_needed()
        self._check_circuit_breaker()
        self._check_symbol(symbol)
        self._check_rate_limit()

        target_mint = WELL_KNOWN_MINTS.get(symbol) or self.jupiter.resolve_mint_by_symbol(symbol)
        usdc_mint = WELL_KNOWN_MINTS["USDC"]

        if action == "open_long":
            notional = position_size(equity_usd, 1.0, self.risk_cfg) if self.risk_cfg else equity_usd * 0.05
            notional = min(notional, self.limits.max_position_usd)
            amount_atomic = int(notional * (10 ** USDC_DECIMALS))
            quote = self._get_quote_or_order(usdc_mint, target_mint, amount_atomic)
            self._check_quote_slippage(quote)
            result = self._sign_and_send(quote)
            self._positions[symbol] = self._positions.get(symbol, 0.0) + float(quote["outAmount"])
            self._audit({"event": "swap", "agent_id": agent_id, "action": action, "symbol": symbol,
                         "usdc_in": notional, "out_amount_atomic": quote["outAmount"], "sig": result,
                         "jupiter_version": "v2" if self.jupiter.settings.use_v2 else "v1"})

        elif action == "close_long":
            held = self._positions.get(symbol, 0.0)
            if held <= 0:
                raise GatewayRejection(f"No hay posición registrada en {symbol} para cerrar")
            quote = self._get_quote_or_order(target_mint, usdc_mint, int(held))
            self._check_quote_slippage(quote)
            result = self._sign_and_send(quote)
            self._positions[symbol] = 0.0
            self._audit({"event": "swap", "agent_id": agent_id, "action": action, "symbol": symbol,
                         "amount_in_atomic": held, "usdc_out_atomic": quote["outAmount"], "sig": result,
                         "jupiter_version": "v2" if self.jupiter.settings.use_v2 else "v1"})
        else:
            raise GatewayRejection(f"Acción no soportada: {action} (Jupiter es spot-only, sin shorts)")

        self._state.order_timestamps.append(time.time())
        return {"signature": result, "quote": quote}

    def _get_quote_or_order(self, input_mint: str, output_mint: str, amount: int) -> dict:
        """
        v2 (/order) trae la cotización Y la transacción ya armada en un
        solo call; v1 (/quote) solo trae la cotización, falta armar la
        transacción en un segundo paso (ver _sign_and_send). Ambas
        respuestas traen `outAmount` y `priceImpactPct` con el mismo
        nombre, así que el resto del gateway no necesita saber cuál se
        está usando.
        """
        if self.jupiter.settings.use_v2:
            return self.jupiter.get_order(input_mint, output_mint, amount, self.wallet.pubkey_str,
                                           self.limits.max_slippage_bps)
        return self.jupiter.get_quote(input_mint, output_mint, amount, self.limits.max_slippage_bps)

    def _sign_and_send(self, quote_or_order: dict) -> str:
        if self.jupiter.settings.use_v2:
            # v2: Jupiter ya armó la transacción en /order (campo "transaction").
            # Se firma y se manda a /execute — Jupiter gestiona el landing
            # (reintentos, fees de prioridad), no hace falta nuestro propio RPC.
            signed_bytes = self.wallet.sign_versioned_tx_b64(quote_or_order["transaction"])
            result = self.jupiter.execute_order(
                base64.b64encode(signed_bytes).decode(), quote_or_order["requestId"]
            )
            signature = result.get("signature")
            if not signature:
                raise RuntimeError(f"/execute no devolvió signature: {result}")
            return signature

        # v1 legacy: hay que armar la transacción, firmarla, Y mandarla por RPC propio.
        swap_tx_b64 = self.jupiter.get_swap_transaction(quote_or_order, self.wallet.pubkey_str)
        signed_bytes = self.wallet.sign_versioned_tx_b64(swap_tx_b64)
        signature = self.rpc.send_raw_transaction(signed_bytes)
        self.rpc.confirm_transaction(signature, timeout_s=30)
        return signature
