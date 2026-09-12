"""
providers.py
============
Adaptadores que envuelven los conectores YA construidos (binance_connector,
bybit_connector, weex_connector, solana_connector) con la misma interfaz
mínima: get_price(asset) y get_ohlcv(asset, timeframe, limit).

No hay código nuevo de conexión a ningún exchange acá — esto es una capa
delgada sobre lo que ya existe y ya está probado.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd

from .models import PriceQuote
from .asset_registry import cex_symbol, NOT_LIQUID_ON_SOLANA


class AssetNotSupportedError(RuntimeError):
    pass


class OHLCVNotAvailableError(RuntimeError):
    """Algunos venues (Solana vía Jupiter) no tienen un endpoint de velas."""


class MarketDataProvider(ABC):
    venue_name: str

    @abstractmethod
    def get_price(self, asset: str, market_type: str = "spot", quote: str = "USDT") -> PriceQuote: ...

    @abstractmethod
    def get_ohlcv(self, asset: str, timeframe: str = "1h", limit: int = 500,
                  market_type: str = "spot", quote: str = "USDT") -> pd.DataFrame: ...


class CEXMarketDataProvider(MarketDataProvider):
    """
    Sirve para Binance, Bybit o Weex indistintamente — los tres
    conectores comparten `get_last_price(symbol)` y `get_ohlcv(symbol,...)`,
    la misma propiedad que ya permitió reutilizar TradingGateway entre
    los tres (ver bybit_connector/tests/test_gateway_reuse.py).
    """
    def __init__(self, connector, venue_name: str):
        self.connector = connector
        self.venue_name = venue_name

    def get_price(self, asset: str, market_type: str = "spot", quote: str = "USDT") -> PriceQuote:
        symbol = cex_symbol(asset, quote, market_type, self.venue_name)
        price = self.connector.get_last_price(symbol)
        return PriceQuote.now(asset, self.venue_name, price, symbol)

    def get_ohlcv(self, asset: str, timeframe: str = "1h", limit: int = 500,
                  market_type: str = "spot", quote: str = "USDT") -> pd.DataFrame:
        symbol = cex_symbol(asset, quote, market_type, self.venue_name)
        return self.connector.get_ohlcv(symbol, timeframe, limit)


# Traduce un timeframe común ("1h", "15m", "1d") al formato de cada proveedor.
# (unidad_gecko, aggregate_gecko, tipo_birdeye, segundos_por_vela)
_TIMEFRAME_MAP = {
    "1m": ("minute", 1, "1m", 60),
    "5m": ("minute", 5, "5m", 300),
    "15m": ("minute", 15, "15m", 900),
    "1h": ("hour", 1, "1H", 3600),
    "4h": ("hour", 4, "4H", 14400),
    "1d": ("day", 1, "1D", 86400),
}


class SolanaMarketDataProvider(MarketDataProvider):
    """
    Jupiter no tiene velas OHLCV — solo cotizaciones de swap puntuales
    (ver get_price). Para get_ohlcv() se usan proveedores externos
    especializados en datos on-chain de Solana, en orden de prioridad:

      1. Birdeye — más especializado en Solana, mejor límite gratis
         (1 req/s vs 30 req/min de GeckoTerminal), pero pide API key
         incluso en el plan gratis.
      2. GeckoTerminal — gratis sin API key, y se puede pedir OHLCV
         directo por dirección de token (usa el pool más líquido
         automáticamente) — más simple de integrar como respaldo.

    Ver market_data/README.md para la comparación completa (incluida
    la investigación sobre cómo Photon no publica qué usa por debajo).
    """
    venue_name = "solana"
    _PROBE_USDC_AMOUNT = 10 * 1_000_000  # 10 USDC (6 decimales) — solo para cotizar, no se ejecuta

    def __init__(self, jupiter_client, birdeye_client=None, geckoterminal_client=None):
        self.jupiter = jupiter_client
        self.birdeye = birdeye_client
        self.geckoterminal = geckoterminal_client

    def get_price(self, asset: str, market_type: str = "spot", quote: str = "USDT") -> PriceQuote:
        asset = asset.upper()
        if asset in NOT_LIQUID_ON_SOLANA:
            raise AssetNotSupportedError(
                f"{asset} muy probablemente no tiene una versión líquida en Solana — "
                f"ver solana_connector/README.md"
            )
        target_mint = self.jupiter.resolve_mint_by_symbol(asset)
        usdc_mint = self.jupiter.resolve_mint_by_symbol("USDC")
        quote_resp = self.jupiter.get_quote(usdc_mint, target_mint, self._PROBE_USDC_AMOUNT)
        out_amount = float(quote_resp["outAmount"])
        if out_amount <= 0:
            raise AssetNotSupportedError(f"Jupiter no devolvió una ruta válida para {asset}")
        price = (self._PROBE_USDC_AMOUNT / 1_000_000) / out_amount
        return PriceQuote.now(asset, "solana", price, f"{asset}/USDC (Jupiter)")

    def get_ohlcv(self, asset: str, timeframe: str = "1h", limit: int = 500,
                  market_type: str = "spot", quote: str = "USDT") -> pd.DataFrame:
        asset = asset.upper()
        if asset in NOT_LIQUID_ON_SOLANA:
            raise AssetNotSupportedError(f"{asset} muy probablemente no líquido en Solana")
        if timeframe not in _TIMEFRAME_MAP:
            raise OHLCVNotAvailableError(f"Timeframe '{timeframe}' no soportado (usar: {list(_TIMEFRAME_MAP)})")

        errors = {}
        if self.birdeye is not None:
            try:
                return self._ohlcv_from_birdeye(asset, timeframe, limit)
            except Exception as e:
                errors["birdeye"] = str(e)
        if self.geckoterminal is not None:
            try:
                return self._ohlcv_from_geckoterminal(asset, timeframe, limit)
            except Exception as e:
                errors["geckoterminal"] = str(e)

        if not errors:
            raise OHLCVNotAvailableError(
                "Jupiter no tiene endpoint de velas propio, y no se configuró ni Birdeye ni "
                "GeckoTerminal como proveedor de respaldo — ver market_data/README.md"
            )
        raise OHLCVNotAvailableError(f"Ningún proveedor de OHLCV pudo responder para {asset}: {errors}")

    def _ohlcv_from_birdeye(self, asset: str, timeframe: str, limit: int) -> pd.DataFrame:
        import time
        _, _, birdeye_type, seconds_per_bar = _TIMEFRAME_MAP[timeframe]
        target_mint = self.jupiter.resolve_mint_by_symbol(asset)
        usdc_mint = self.jupiter.resolve_mint_by_symbol("USDC")
        now = int(time.time())
        items = self.birdeye.get_ohlcv_base_quote(
            target_mint, usdc_mint, birdeye_type, now - seconds_per_bar * limit, now
        )
        df = pd.DataFrame(items)[["unixTime", "o", "h", "l", "c", "v"]]
        df.columns = ["ts", "open", "high", "low", "close", "volume"]
        df["ts"] = pd.to_datetime(df["ts"], unit="s")
        return df.set_index("ts")

    def _ohlcv_from_geckoterminal(self, asset: str, timeframe: str, limit: int) -> pd.DataFrame:
        gecko_unit, gecko_aggregate, _, _ = _TIMEFRAME_MAP[timeframe]
        target_mint = self.jupiter.resolve_mint_by_symbol(asset)
        rows = self.geckoterminal.get_ohlcv_by_token(target_mint, gecko_unit, gecko_aggregate, limit)
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="s")
        return df.set_index("ts").sort_index()
