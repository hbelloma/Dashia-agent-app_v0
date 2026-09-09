"""
backtest.py
===========
Simulador de ejecución sobre las señales producidas por strategy.py.
Aplica el mismo criterio de dimensionamiento y SL/TP que la sección
"STRATEGY ENTRY/EXIT" del pine (líneas ~965-991).
"""

from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from .risk import RiskConfig, position_size, sl_tp_levels


@dataclass
class Trade:
    side: str
    entry_time: object
    entry_price: float
    exit_time: object = None
    exit_price: float = None
    qty: float = 0.0
    exit_reason: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class BacktestResult:
    trades: list = field(default_factory=list)
    equity_curve: pd.Series = None
    initial_capital: float = 10_000.0

    @property
    def final_equity(self) -> float:
        return float(self.equity_curve.iloc[-1]) if self.equity_curve is not None else self.initial_capital

    @property
    def total_return_pct(self) -> float:
        return (self.final_equity / self.initial_capital - 1) * 100

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for tr in self.trades if tr.pnl > 0)

    @property
    def losses(self) -> int:
        return sum(1 for tr in self.trades if tr.pnl <= 0)

    @property
    def win_rate_pct(self) -> float:
        return 100 * self.wins / self.total_trades if self.total_trades else 0.0

    @property
    def win_loss_ratio(self) -> float:
        avg_win = np.mean([tr.pnl for tr in self.trades if tr.pnl > 0]) if self.wins else 0.0
        avg_loss = -np.mean([tr.pnl for tr in self.trades if tr.pnl <= 0]) if self.losses else 0.0
        return (avg_win / avg_loss) if avg_loss else float("nan")

    @property
    def max_drawdown_pct(self) -> float:
        if self.equity_curve is None:
            return 0.0
        roll_max = self.equity_curve.cummax()
        dd = (self.equity_curve - roll_max) / roll_max
        return float(dd.min() * 100)

    def summary(self) -> dict:
        return {
            "capital_inicial": self.initial_capital,
            "capital_final": round(self.final_equity, 2),
            "retorno_total_%": round(self.total_return_pct, 2),
            "operaciones": self.total_trades,
            "ganadoras": self.wins,
            "perdedoras": self.losses,
            "win_rate_%": round(self.win_rate_pct, 2),
            "ratio_ganancia_perdida": round(self.win_loss_ratio, 2) if self.total_trades else None,
            "max_drawdown_%": round(self.max_drawdown_pct, 2),
        }


def run_backtest(df: pd.DataFrame, risk_cfg: RiskConfig,
                  initial_capital: float = 10_000.0) -> BacktestResult:
    equity = initial_capital
    equity_curve = []
    trades: list[Trade] = []
    position: Trade | None = None
    sl_level = tp_level = None

    idx = df.index
    o, h, l, c = df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    atr = df["atr"].to_numpy()
    start_long = df["start_long"].to_numpy()
    start_short = df["start_short"].to_numpy()
    end_long = df["end_long"].to_numpy()
    end_short = df["end_short"].to_numpy()

    def close_position(t: int, price: float, reason: str):
        nonlocal equity, position
        if position is None:
            return
        if position.side == "long":
            pnl = (price - position.entry_price) * position.qty
        else:
            pnl = (position.entry_price - price) * position.qty
        position.exit_time, position.exit_price = idx[t], price
        position.exit_reason = reason
        position.pnl = pnl
        position.pnl_pct = pnl / (position.entry_price * position.qty) * 100
        equity += pnl
        trades.append(position)
        position = None

    for t in range(len(df)):
        # 1) Revisar SL/TP intrabar de la posición abierta (si hay)
        if position is not None and (sl_level is not None or tp_level is not None):
            if position.side == "long":
                if sl_level is not None and l[t] <= sl_level:
                    close_position(t, sl_level, "stop_loss")
                elif tp_level is not None and h[t] >= tp_level:
                    close_position(t, tp_level, "take_profit")
            else:
                if sl_level is not None and h[t] >= sl_level:
                    close_position(t, sl_level, "stop_loss")
                elif tp_level is not None and l[t] <= tp_level:
                    close_position(t, tp_level, "take_profit")

        # 2) Salidas por señal (end_long / end_short)
        if position is not None:
            if position.side == "long" and end_long[t]:
                close_position(t, c[t], "signal_exit")
            elif position.side == "short" and end_short[t]:
                close_position(t, c[t], "signal_exit")

        # 3) Nuevas entradas (si estamos flat)
        if position is None:
            if start_long[t]:
                qty = position_size(equity, c[t], risk_cfg)
                if qty > 0:
                    position = Trade(side="long", entry_time=idx[t], entry_price=c[t], qty=qty)
                    sl_level, tp_level = sl_tp_levels(c[t], True, risk_cfg, atr[t])
            elif start_short[t]:
                qty = position_size(equity, c[t], risk_cfg)
                if qty > 0:
                    position = Trade(side="short", entry_time=idx[t], entry_price=c[t], qty=qty)
                    sl_level, tp_level = sl_tp_levels(c[t], False, risk_cfg, atr[t])

        mark_to_market = equity
        if position is not None:
            if position.side == "long":
                mark_to_market += (c[t] - position.entry_price) * position.qty
            else:
                mark_to_market += (position.entry_price - c[t]) * position.qty
        equity_curve.append(mark_to_market)

    if position is not None:
        close_position(len(df) - 1, c[-1], "end_of_data")
        equity_curve[-1] = equity

    result = BacktestResult(trades=trades,
                             equity_curve=pd.Series(equity_curve, index=idx),
                             initial_capital=initial_capital)
    return result
