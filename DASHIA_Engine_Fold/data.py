"""
data.py
=======
Este entorno de pruebas no tiene salida de red hacia Binance/Bybit/etc.,
así que para la demo se genera una serie OHLCV sintética (movimiento
browniano geométrico con volatilidad variable, para simular tramos
alcistas/bajistas realistas). En producción, esta función se reemplaza
por el conector real (REST/WebSocket del exchange o RPC de Solana).
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def synthetic_ohlcv(n_bars: int = 800, start_price: float = 60_000.0,
                     seed: int = 7, freq: str = "1h") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Volatilidad y deriva variables para simular tramos de tendencia distintos
    regime_len = n_bars // 4
    drift = np.concatenate([
        np.full(regime_len, 0.0006),
        np.full(regime_len, -0.0009),
        np.full(regime_len, 0.0004),
        np.full(n_bars - 3 * regime_len, 0.0011),
    ])
    vol = 0.012 + 0.006 * np.sin(np.linspace(0, 6, n_bars)) ** 2
    returns = rng.normal(drift, vol)
    close = start_price * np.exp(np.cumsum(returns))

    high = close * (1 + np.abs(rng.normal(0, 0.004, n_bars)))
    low = close * (1 - np.abs(rng.normal(0, 0.004, n_bars)))
    open_ = np.roll(close, 1)
    open_[0] = start_price
    volume = rng.lognormal(mean=9, sigma=0.5, size=n_bars)

    idx = pd.date_range("2024-01-01", periods=n_bars, freq=freq)
    df = pd.DataFrame({"open": open_, "high": high, "low": low,
                        "close": close, "volume": volume}, index=idx)
    # Asegurar high >= max(open,close) y low <= min(open,close)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return df


def load_csv(path: str) -> pd.DataFrame:
    """
    Carga un CSV con columnas: timestamp, open, high, low, close, volume.
    Útil para correr DASHIA sobre datos históricos reales exportados desde
    un exchange (p. ej. vía ccxt) fuera de este entorno sandbox.
    """
    df = pd.read_csv(path, parse_dates=["timestamp"]).set_index("timestamp")
    df.columns = [c.lower() for c in df.columns]
    return df[["open", "high", "low", "close", "volume"]]
