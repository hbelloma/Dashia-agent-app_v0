"""
lorentzian.py
=============
Núcleo del modelo ML de DASHIA: Approximate Nearest Neighbors con
distancia Lorentziana. Port literal del bloque "Core ML Logic"
(líneas ~815-845 del pine original), incluyendo su comportamiento real
(no el que sugiere el comentario):

- El vecindario de referencia NO es una ventana reciente deslizante: son
  las primeras `maxBarsBack` barras del histórico completo. Una vez el
  precio avanza más allá de esa ventana, el modelo se sigue comparando
  contra ese mismo bloque fijo de barras (así es como lo escribió el
  autor original; se preserva tal cual).
- El filtro "cada 4 barras" del comentario en realidad EXCLUYE los
  múltiplos de 4 (`i % 4` es verdadero cuando i no es múltiplo de 4).
  Se preserva literalmente.
- La etiqueta de entrenamiento compara el precio de hace 4 barras con el
  actual y asigna "short" cuando el precio subió y "long" cuando bajó tal
  como está escrito en el pine (Label.new(long=1, short=-1)). Se deja tal
  cual con una bandera `invert_labels` para que puedan probar la
  convención opuesta y comparar cuál reproduce mejor el backtest real de
  TradingView.
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

from .indicators import FEATURE_FUNCS


@dataclass
class FeatureConfig:
    name: str      # "RSI", "WT", "CCI", "ADX", "STOCHK", "STOCHD", "MFI", "RVI", "ADX2"
    param_a: int
    param_b: int = 1


DEFAULT_FEATURES = [
    FeatureConfig("STOCHK", 14, 3),
    FeatureConfig("STOCHD", 14, 3),
    FeatureConfig("RSI", 14, 2),
    FeatureConfig("ADX", 20, 2),
    FeatureConfig("MFI", 14, 2),
    FeatureConfig("RVI", 14, 2),
    FeatureConfig("WT", 10, 11),
    FeatureConfig("CCI", 20, 2),
    FeatureConfig("RSI", 9, 2),
    FeatureConfig("ADX2", 20, 2),
]


def build_feature_matrix(df: pd.DataFrame, features: list[FeatureConfig],
                          feature_count: int) -> np.ndarray:
    cols = []
    for f in features[:feature_count]:
        series = FEATURE_FUNCS[f.name](df, f.param_a, f.param_b)
        cols.append(series.fillna(0.5).to_numpy())
    return np.column_stack(cols)  # shape (T, feature_count)


def build_training_labels(close: pd.Series, invert_labels: bool = False) -> np.ndarray:
    c = close.to_numpy(dtype=float)
    T = len(c)
    y = np.zeros(T, dtype=int)
    short_label, long_label = (1, -1) if invert_labels else (-1, 1)
    for t in range(4, T):
        if c[t - 4] < c[t]:
            y[t] = short_label
        elif c[t - 4] > c[t]:
            y[t] = long_label
    return y


def lorentzian_ann(feature_matrix: np.ndarray, y_train: np.ndarray,
                    neighbors_count: int, max_bars_back: int) -> np.ndarray:
    """
    Devuelve `prediction[t]`: suma de las etiquetas de los k vecinos
    aproximados más cercanos (por distancia Lorentziana) a la barra t,
    igual que `prediction := array.sum(predictions)` en el pine.
    """
    T = feature_matrix.shape[0]
    max_bars_back_index = max(0, T - max_bars_back)
    prediction = np.zeros(T)

    for t in range(max_bars_back_index, T):
        size_loop = min(max_bars_back - 1, t)
        distances: list[float] = []
        predictions: list[int] = []
        last_distance = -1.0
        row_t = feature_matrix[t]
        for i in range(0, size_loop + 1):
            if i % 4 == 0:
                continue
            d = float(np.sum(np.log1p(np.abs(row_t - feature_matrix[i]))))
            if d >= last_distance:
                last_distance = d
                distances.append(d)
                predictions.append(int(y_train[i]))
                if len(predictions) > neighbors_count:
                    idx = min(round(neighbors_count * 3 / 4), len(distances) - 1)
                    last_distance = distances[idx]
                    distances.pop(0)
                    predictions.pop(0)
        prediction[t] = float(sum(predictions))
    return prediction
