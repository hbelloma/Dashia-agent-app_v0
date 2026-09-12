"""
filters.py
==========
Filtros que ajustan la frecuencia de señales del modelo ML
(sección "Filters" del pine, líneas ~340-390) más los filtros de
tendencia EMA/SMA usados en las condiciones de entrada.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from .indicators import ema, sma, rma, true_range, rsi, _stoch_of


def regime_filter(ohlc4: pd.Series, high: pd.Series, low: pd.Series,
                   threshold: float, enabled: bool) -> pd.Series:
    n = len(ohlc4)
    src = ohlc4.to_numpy(dtype=float)
    h = high.to_numpy(dtype=float)
    l = low.to_numpy(dtype=float)
    value1 = np.zeros(n)
    value2 = np.zeros(n)
    klmf = np.zeros(n)
    for t in range(1, n):
        value1[t] = 0.2 * (src[t] - src[t - 1]) + 0.8 * value1[t - 1]
        value2[t] = 0.1 * (h[t] - l[t]) + 0.8 * value2[t - 1]
        omega = abs(value1[t] / value2[t]) if value2[t] != 0 else 0.0
        alpha = (-omega ** 2 + np.sqrt(omega ** 4 + 16 * omega ** 2)) / 8 if omega != 0 else 0.0
        klmf[t] = alpha * src[t] + (1 - alpha) * klmf[t - 1]
    klmf_s = pd.Series(klmf, index=ohlc4.index)
    abs_slope = (klmf_s - klmf_s.shift(1)).abs()
    avg_abs_slope = ema(abs_slope, 200)
    normalized_slope_decline = (abs_slope - avg_abs_slope) / avg_abs_slope.replace(0, np.nan)
    passes = normalized_slope_decline >= threshold
    return passes.fillna(False) if enabled else pd.Series(True, index=ohlc4.index)


def raw_adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)
    tr_s = rma(true_range(high, low, close), length)
    di_plus = 100 * rma(plus_dm, length) / tr_s.replace(0, np.nan)
    di_minus = 100 * rma(minus_dm, length) / tr_s.replace(0, np.nan)
    dx = (100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)).fillna(0.0)
    return rma(dx, length)


def filter_adx(high, low, close, length: int, threshold: int, enabled: bool) -> pd.Series:
    if not enabled:
        return pd.Series(True, index=close.index)
    return raw_adx(high, low, close, length) > threshold


def filter_volatility(high, low, close, min_len: int, max_len: int, enabled: bool) -> pd.Series:
    if not enabled:
        return pd.Series(True, index=close.index)
    tr = true_range(high, low, close)
    recent_atr = rma(tr, min_len)
    hist_atr = rma(tr, max_len)
    return recent_atr > hist_atr


def kd_lines(src: pd.Series, n1: int, n3: int):
    rsi1 = rsi(src, n1)
    k = sma(_stoch_of(rsi1, n1), 3)
    d = sma(k, n3)
    return k, d


def filter_kd_crossover(src, n1, n3, enabled: bool) -> pd.Series:
    if not enabled:
        return pd.Series(True, index=src.index)
    k, d = kd_lines(src, n1, n3)
    return (k > d) & (k.shift(1) <= d.shift(1))


def filter_kd_crossunder(src, n1, n3, enabled: bool) -> pd.Series:
    if not enabled:
        return pd.Series(True, index=src.index)
    k, d = kd_lines(src, n1, n3)
    return (k < d) & (k.shift(1) >= d.shift(1))


def ema_trend(close: pd.Series, period: int, enabled: bool):
    if not enabled:
        true_s = pd.Series(True, index=close.index)
        return true_s, true_s
    e = ema(close, period)
    return close > e, close < e


def sma_trend(close: pd.Series, period: int, enabled: bool):
    if not enabled:
        true_s = pd.Series(True, index=close.index)
        return true_s, true_s
    s = sma(close, period)
    return close > s, close < s
