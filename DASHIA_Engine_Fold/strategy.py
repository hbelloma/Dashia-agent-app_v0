"""
strategy.py
===========
Ensambla el pipeline completo de DASHIA: features -> ANN Lorentziano ->
filtro de kernel -> filtros de tendencia/régimen -> señales de entrada y
salida. Réplica de la sección "Entries and Exits" (líneas ~905-935).

Se implementa el modo de salida ESTRICTO (bar-count, el modo por
defecto del script: useDynamicExits=false). El modo de salida dinámico
basado en cambios de pendiente del kernel queda documentado como
extensión pendiente en el README del paquete.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from .indicators import true_range, rma
from .lorentzian import (DEFAULT_FEATURES, FeatureConfig, build_feature_matrix,
                          build_training_labels, lorentzian_ann)
from .kernels import rational_quadratic, gaussian
from .filters import (regime_filter, filter_adx, filter_volatility,
                       filter_kd_crossover, filter_kd_crossunder,
                       ema_trend, sma_trend)
from .risk import RiskConfig


@dataclass
class DashiaConfig:
    neighbors_count: int = 8
    max_bars_back: int = 300          # 8000 en TradingView; se reduce para backtests locales
    feature_count: int = 10
    features: list = field(default_factory=lambda: DEFAULT_FEATURES)
    invert_labels: bool = False

    use_kernel_filter: bool = True
    kernel_lookback: int = 8
    kernel_relative_weight: float = 8.0
    kernel_regression_level: int = 25
    kernel_lag: int = 2
    use_kernel_smoothing: bool = False

    use_volatility_filter: bool = False
    use_regime_filter: bool = False
    regime_threshold: float = -0.1
    use_adx_filter: bool = False
    adx_threshold: int = 20
    use_kd_cross_filter: bool = True

    use_ema_filter: bool = False
    ema_period: int = 200
    use_sma_filter: bool = False
    sma_period: int = 200

    risk: RiskConfig = field(default_factory=RiskConfig)


def run_dashia(df: pd.DataFrame, cfg: DashiaConfig) -> pd.DataFrame:
    """
    df: DataFrame con columnas open, high, low, close, volume (index = tiempo).
    Devuelve el mismo df con columnas añadidas: prediction, signal,
    start_long, start_short, end_long, end_short, atr.
    """
    df = df.copy()
    df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3
    df["ohlc4"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4

    feature_matrix = build_feature_matrix(df, cfg.features, cfg.feature_count)
    y_train = build_training_labels(df["close"], cfg.invert_labels)
    prediction = lorentzian_ann(feature_matrix, y_train, cfg.neighbors_count, cfg.max_bars_back)
    df["prediction"] = prediction

    f_volatility = filter_volatility(df["high"], df["low"], df["close"], 1, 10, cfg.use_volatility_filter)
    f_regime = regime_filter(df["ohlc4"], df["high"], df["low"], cfg.regime_threshold, cfg.use_regime_filter)
    f_adx = filter_adx(df["high"], df["low"], df["close"], 14, cfg.adx_threshold, cfg.use_adx_filter)
    filter_all = f_volatility & f_regime & f_adx

    raw_signal = np.where(
        (df["prediction"].to_numpy() > 0) & filter_all.to_numpy(), 1,
        np.where((df["prediction"].to_numpy() < 0) & filter_all.to_numpy(), -1, np.nan),
    )
    signal = pd.Series(raw_signal, index=df.index).ffill().fillna(0).astype(int)
    df["signal"] = signal

    is_ema_up, is_ema_down = ema_trend(df["close"], cfg.ema_period, cfg.use_ema_filter)
    is_sma_up, is_sma_down = sma_trend(df["close"], cfg.sma_period, cfg.use_sma_filter)
    is_kd_co = filter_kd_crossover(df["close"], 14, 3, cfg.use_kd_cross_filter)
    is_kd_cu = filter_kd_crossunder(df["close"], 14, 3, cfg.use_kd_cross_filter)

    is_buy_signal = (signal == 1) & is_ema_up & is_sma_up & is_kd_co
    is_sell_signal = (signal == -1) & is_ema_down & is_sma_down & is_kd_cu
    is_different_signal = signal.diff().fillna(0) != 0
    is_new_buy = is_buy_signal & is_different_signal
    is_new_sell = is_sell_signal & is_different_signal

    # --- Filtro de kernel (Rational Quadratic + Gaussian) ---
    if cfg.use_kernel_filter:
        yhat1 = rational_quadratic(df["close"], cfg.kernel_lookback,
                                    cfg.kernel_relative_weight, cfg.kernel_regression_level)
        yhat2 = gaussian(df["close"], cfg.kernel_lookback - cfg.kernel_lag, cfg.kernel_regression_level)
        is_bearish_rate = yhat1.shift(1) > yhat1
        is_bullish_rate = yhat1.shift(1) < yhat1
        is_bullish_smooth = yhat2 >= yhat1
        is_bearish_smooth = yhat2 <= yhat1
        is_bullish = is_bullish_smooth if cfg.use_kernel_smoothing else is_bullish_rate
        is_bearish = is_bearish_smooth if cfg.use_kernel_smoothing else is_bearish_rate
    else:
        is_bullish = pd.Series(True, index=df.index)
        is_bearish = pd.Series(True, index=df.index)

    start_long = (is_new_buy & is_bullish & is_ema_up & is_sma_up).fillna(False)
    start_short = (is_new_sell & is_bearish & is_ema_down & is_sma_down).fillna(False)
    df["start_long"] = start_long
    df["start_short"] = start_short

    # --- Salida estricta por conteo de barras (modo por defecto) ---
    signal_change = signal.diff().fillna(0) != 0
    bars_held = np.zeros(len(df), dtype=int)
    held = 0
    sig_arr = signal.to_numpy()
    for t in range(len(df)):
        if t > 0 and sig_arr[t] != sig_arr[t - 1]:
            held = 0
        else:
            held += 1
        bars_held[t] = held
    is_held_4 = bars_held == 4
    is_held_lt_4 = (bars_held > 0) & (bars_held < 4)

    is_last_buy = (signal.shift(4) == 1) & is_ema_up.shift(4).fillna(False) & is_sma_up.shift(4).fillna(False)
    is_last_sell = (signal.shift(4) == -1) & is_ema_down.shift(4).fillna(False) & is_sma_down.shift(4).fillna(False)

    end_long = (((is_held_4 & is_last_buy) |
                 (is_held_lt_4 & is_new_sell & is_last_buy)) & start_long.shift(4).fillna(False))
    end_short = (((is_held_4 & is_last_sell) |
                  (is_held_lt_4 & is_new_buy & is_last_sell)) & start_short.shift(4).fillna(False))
    df["end_long"] = end_long.fillna(False)
    df["end_short"] = end_short.fillna(False)

    df["atr"] = rma(true_range(df["high"], df["low"], df["close"]), 14)
    return df
