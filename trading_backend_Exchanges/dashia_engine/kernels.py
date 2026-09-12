"""
kernels.py
==========
Nadaraya-Watson kernel regression: Rational Quadratic y Gaussian.
Referencia: sección "Kernels" del pine de DASHIA (líneas ~305-340).

Nota de fidelidad: el pine original arma la ventana con
`array.from(_src)` sobre un valor escalar, lo que en la práctica colapsa
el tamaño de la ventana a 1-2 barras (muy probablemente no era la
intención del autor). Aquí se implementa la versión estándar y publicada
de este kernel (misma fórmula de pesos, ventana de `lookback` barras hacia
atrás, acotada por `max_window` por rendimiento), que es la que de hecho
usan la mayoría de forks funcionales de este indicador. Se documenta este
supuesto para que puedan validarlo contra la salida real de TradingView.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def rational_quadratic(src: pd.Series, lookback: int, relative_weight: float,
                        start_at_bar: int, max_window: int = 500) -> pd.Series:
    values = src.to_numpy(dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    window = min(max_window, lookback + start_at_bar + 50)
    # pesos precalculados: w(i) = (1 + i^2 / (lookback^2 * 2 * relative_weight)) ^ -relative_weight
    i_arr = np.arange(window)
    w = np.power(1.0 + (i_arr ** 2) / (lookback ** 2 * 2.0 * relative_weight), -relative_weight)
    for t in range(n):
        lo = max(0, t - window + 1)
        seg = values[lo:t + 1][::-1]  # seg[0] = barra actual, seg[i] = i barras atrás
        wi = w[:len(seg)]
        cw = wi.sum()
        if cw > 0:
            out[t] = float(np.dot(seg, wi) / cw)
    return pd.Series(out, index=src.index)


def gaussian(src: pd.Series, lookback: int, start_at_bar: int,
             max_window: int = 500) -> pd.Series:
    values = src.to_numpy(dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    window = min(max_window, lookback + start_at_bar + 50)
    i_arr = np.arange(window)
    w = np.exp(-(i_arr ** 2) / (2.0 * lookback ** 2))
    for t in range(n):
        lo = max(0, t - window + 1)
        seg = values[lo:t + 1][::-1]
        wi = w[:len(seg)]
        cw = wi.sum()
        if cw > 0:
            out[t] = float(np.dot(seg, wi) / cw)
    return pd.Series(out, index=src.index)
