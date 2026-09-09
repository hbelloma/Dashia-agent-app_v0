"""
risk.py
=======
Planes de riesgo y cálculo de tamaño de posición / SL-TP, réplica de la
sección de gestión de riesgo del pine (líneas ~20-45 y ~935-965).
"""

from __future__ import annotations
from dataclasses import dataclass

RISK_PLANS = {
    "COOK": {"max_drawdown_pct": 10, "leverage_hint": "x1"},
    "WALK": {"max_drawdown_pct": 30, "leverage_hint": "x2-x5"},
    "HAWK": {"max_drawdown_pct": 50, "leverage_hint": "x10-x100"},
    "ALLIN": {"max_drawdown_pct": 100, "leverage_hint": "sin límite"},
}


@dataclass
class RiskConfig:
    plan: str = "ALLIN"
    risk_capital_pct: float = 100.0       # % del equity destinado a cada entrada
    sltp_method: str = "NONE"             # NONE | PERCENTAGE | ATR
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 10.0
    sl_atr_mult: float = 1.0
    tp_atr_mult: float = 5.0
    use_trailing: bool = False
    trail_pct: float = 1.0

    @property
    def max_drawdown_pct(self) -> float:
        return RISK_PLANS[self.plan]["max_drawdown_pct"]


def position_size(equity: float, price: float, cfg: RiskConfig) -> float:
    """
    Réplica exacta de:
    qty1 = (equity * riskCapital/100) / (close * stopLoss/100)
    qty1 := (qty1*close >= equity) ? (equity/close) : qty1
    Nota: la fórmula del pine usa el % de Stop Loss para dimensionar la
    posición incluso cuando el método de SL/TP activo es distinto — se
    conserva tal cual.
    """
    sl_pct = max(cfg.stop_loss_pct, 0.05)
    qty = (equity * cfg.risk_capital_pct / 100.0) / (price * sl_pct / 100.0)
    if qty * price >= equity:
        qty = equity / price
    return max(qty, 0.0)


def sl_tp_levels(entry_price: float, is_long: bool, cfg: RiskConfig, atr_value: float | None):
    """Devuelve (stop_loss, take_profit) o (None, None) si SLTPMethod == NONE."""
    if cfg.sltp_method == "PERCENTAGE":
        if is_long:
            return (entry_price * (1 - cfg.stop_loss_pct / 100),
                    entry_price * (1 + cfg.take_profit_pct / 100))
        return (entry_price * (1 + cfg.stop_loss_pct / 100),
                entry_price * (1 - cfg.take_profit_pct / 100))
    if cfg.sltp_method == "ATR" and atr_value:
        if is_long:
            return (entry_price - cfg.sl_atr_mult * atr_value,
                     entry_price + cfg.tp_atr_mult * atr_value)
        return (entry_price + cfg.sl_atr_mult * atr_value,
                entry_price - cfg.tp_atr_mult * atr_value)
    return (None, None)
