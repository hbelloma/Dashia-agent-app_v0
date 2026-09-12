"""
indicators.py
=============
Port fiel de las funciones de features del Pine Script de DASHIA
(sección "NORMALIZED INDICATOR FUNCTIONS", líneas ~185-280 del original).

Cada indicador ta.* de Pine se reconstruye aquí sobre pandas/numpy, y cada
función n_xxx() replica la normalización que el script aplica antes de
usar el indicador como feature del modelo ANN (rescale a un rango fijo o
normalize con mínimo/máximo histórico corredizo, igual que el `var
_historicMin/_historicMax` de Pine).

Todas las funciones reciben y devuelven pandas.Series alineadas al índice
del DataFrame OHLCV.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers de bajo nivel (equivalentes a ta.ema, ta.rma, ta.sma, ta.stdev...)
# ---------------------------------------------------------------------------

def ema(src: pd.Series, length: int) -> pd.Series:
    """Equivalente a ta.ema(src, length)."""
    return src.ewm(span=length, adjust=False, min_periods=length).mean()


def rma(src: pd.Series, length: int) -> pd.Series:
    """
    Equivalente a ta.rma(src, length) (suavizado de Wilder).
    Es matemáticamente una EWM con alpha = 1/length. Se usa para RSI, ADX, etc.
    """
    return src.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def sma(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(length, min_periods=length).mean()


def stdev(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(length, min_periods=length).std(ddof=0)


def mean_abs_dev(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(length, min_periods=length).apply(
        lambda w: np.mean(np.abs(w - w.mean())), raw=True
    )


def rescale(src: pd.Series, old_min: float, old_max: float,
            new_min: float, new_max: float) -> pd.Series:
    """Equivalente a rescale(): reescalado lineal con límites FIJOS conocidos."""
    return new_min + (new_max - new_min) * (src - old_min) / max(old_max - old_min, 1e-9)


def normalize_running(src: pd.Series, new_min: float, new_max: float) -> pd.Series:
    """
    Equivalente a normalize(): usa mínimo/máximo HISTÓRICO corredizo
    (como el `var _historicMin/_historicMax` de Pine), no una ventana fija.
    """
    hist_min = src.cummin()
    hist_max = src.cummax()
    return new_min + (new_max - new_min) * (src - hist_min) / (hist_max - hist_min).clip(lower=1e-9)


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)


def rsi(src: pd.Series, length: int) -> pd.Series:
    delta = src.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(50.0)


def _stoch_of(src: pd.Series, length: int) -> pd.Series:
    """ta.stoch(src, src, src, length): estocástico de una sola serie contra sí misma."""
    lo = src.rolling(length, min_periods=length).min()
    hi = src.rolling(length, min_periods=length).max()
    return 100 * (src - lo) / (hi - lo).replace(0, np.nan)


# ---------------------------------------------------------------------------
# Features normalizados n_xxx (idénticos en intención a los del pine)
# ---------------------------------------------------------------------------

def n_rsi(src: pd.Series, n1: int, n2: int) -> pd.Series:
    return rescale(ema(rsi(src, n1), n2), 0, 100, 0, 1)


def n_stochk(src: pd.Series, n1: int, n2: int) -> pd.Series:
    rsi1 = rsi(src, n1)
    k = sma(_stoch_of(rsi1, n1), n2)
    return rescale(k, 0, 100, 0, 1)


def n_stochd(src: pd.Series, n1: int, n3: int) -> pd.Series:
    rsi1 = rsi(src, n1)
    k = sma(_stoch_of(rsi1, n1), 3)
    d = sma(k, n3)
    return rescale(d, 0, 100, 0, 1)


def n_mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
          n1: int, n2: int) -> pd.Series:
    tp = (high + low + close) / 3
    raw_mf = tp * volume
    d_tp = tp.diff()
    pos_mf = raw_mf.where(d_tp > 0, 0.0).rolling(n1, min_periods=n1).sum()
    neg_mf = raw_mf.where(d_tp < 0, 0.0).rolling(n1, min_periods=n1).sum()
    mfr = pos_mf / neg_mf.replace(0, np.nan)
    mfi = (100 - 100 / (1 + mfr)).fillna(50.0)
    return rescale(ema(mfi, n2), 0, 100, 0, 1)


def n_rvi(src: pd.Series, n1: int, n2: int) -> pd.Series:
    sd = stdev(src, n1)
    change = src.diff()
    upper = ema(pd.Series(np.where(change <= 0, 0.0, sd), index=src.index), n1)
    lower = ema(pd.Series(np.where(change > 0, 0.0, sd), index=src.index), n1)
    rvi = (upper / (upper + lower).replace(0, np.nan) * 100).fillna(50.0)
    return rescale(ema(rvi, n2), 0, 100, 0, 1)


def n_cci(src: pd.Series, n1: int, n2: int) -> pd.Series:
    dev = mean_abs_dev(src, n1)
    cci = (src - sma(src, n1)) / (0.015 * dev.replace(0, np.nan))
    return normalize_running(ema(cci.fillna(0.0), n2), 0, 1)


def n_wt(hlc3: pd.Series, n1: int = 10, n2: int = 11) -> pd.Series:
    ema1 = ema(hlc3, n1)
    ema2 = ema((hlc3 - ema1).abs(), n1)
    ci = (hlc3 - ema1) / (0.015 * ema2.replace(0, np.nan))
    wt1 = ema(ci.fillna(0.0), n2)
    wt2 = sma(wt1, 4)
    return normalize_running(wt1 - wt2, 0, 1)


def n_adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """
    Réplica del ADX de Wilder. La recursión "suma suavizada" del pine
    (trSmooth := trSmooth[1] - trSmooth[1]/length + tr) es algebraicamente
    equivalente a usar rma() en numerador y denominador (el factor de escala
    se cancela en el cociente DI+/DI-), así que aquí se usa rma()
    directamente: da el mismo ADX de forma vectorizada.
    """
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)
    tr = true_range(high, low, close)
    tr_s = rma(tr, length)
    di_plus = 100 * rma(plus_dm, length) / tr_s.replace(0, np.nan)
    di_minus = 100 * rma(minus_dm, length) / tr_s.replace(0, np.nan)
    dx = (100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)).fillna(0.0)
    adx = rma(dx, length)
    return rescale(adx, 0, 100, 0, 1)


FEATURE_FUNCS = {
    "RSI": lambda df, a, b: n_rsi(df["close"], a, b),
    "WT": lambda df, a, b: n_wt(df["hlc3"], a, b),
    "CCI": lambda df, a, b: n_cci(df["close"], a, b),
    "ADX": lambda df, a, b: n_adx(df["high"], df["low"], df["close"], a),
    "ADX2": lambda df, a, b: n_adx(df["high"], df["low"], df["close"], a),
    "STOCHK": lambda df, a, b: n_stochk(df["close"], a, b),
    "STOCHD": lambda df, a, b: n_stochd(df["close"], a, b),
    "MFI": lambda df, a, b: n_mfi(df["high"], df["low"], df["close"], df["volume"], a, b),
    "RVI": lambda df, a, b: n_rvi(df["close"], a, b),
}
