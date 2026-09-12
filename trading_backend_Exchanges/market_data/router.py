"""
router.py
=========
El punto de entrada que responde "pídeme BTC" sin que quien pregunta
sepa (ni le importe) si viene de Binance, Bybit, Weex o Solana.

Estrategia: para cada activo hay un orden de prioridad de venues
(asset_registry.venue_priority_for). Se intenta el primero; si falla
(el venue no tiene ese par, no está conectado, error de red), se pasa
al siguiente — no se asume de antemano que la tabla de prioridad es
perfecta, se comprueba en la práctica y con fallback real.
"""

from __future__ import annotations
import time
import logging
from dataclasses import dataclass, field

from .asset_registry import venue_priority_for
from .models import PriceQuote

log = logging.getLogger("market_data")


class NoVenueAvailableError(RuntimeError):
    def __init__(self, asset: str, attempts: dict):
        self.attempts = attempts
        detail = "; ".join(f"{v}: {e}" for v, e in attempts.items())
        super().__init__(f"Ningún venue disponible pudo dar el precio de {asset}. Intentos: {detail}")


@dataclass
class _CacheEntry:
    quote: PriceQuote
    expires_at: float


class UnifiedMarketData:
    def __init__(self, providers: dict, cache_ttl_s: float = 5.0):
        """
        providers: {"binance": CEXMarketDataProvider(...), "solana": SolanaMarketDataProvider(...), ...}
        Solo se registran los venues que el usuario realmente tiene
        conectados — ver build_market_data_for_user() en vault_bridge.py.
        """
        self.providers = providers
        self.cache_ttl_s = cache_ttl_s
        self._cache: dict[tuple, _CacheEntry] = {}

    @property
    def available_venues(self) -> list[str]:
        return list(self.providers.keys())

    def get_price(self, asset: str, venue: str | None = None, market_type: str = "spot",
                  quote: str = "USDT", use_cache: bool = True) -> PriceQuote:
        asset = asset.upper()
        cache_key = (asset, venue, market_type, quote)
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached and cached.expires_at > time.time():
                return cached.quote

        if venue is not None:
            candidates = [venue]
        else:
            candidates = [v for v in venue_priority_for(asset) if v in self.providers]
            if not candidates:
                candidates = list(self.providers.keys())  # sin prioridad conocida, probar lo que haya

        attempts = {}
        for v in candidates:
            provider = self.providers.get(v)
            if provider is None:
                attempts[v] = "no conectado para este usuario"
                continue
            try:
                result = provider.get_price(asset, market_type=market_type, quote=quote)
                if use_cache:
                    self._cache[cache_key] = _CacheEntry(result, time.time() + self.cache_ttl_s)
                return result
            except Exception as e:
                log.info("Venue %s falló para %s: %s", v, asset, e)
                attempts[v] = str(e)

        raise NoVenueAvailableError(asset, attempts)

    def get_ohlcv(self, asset: str, timeframe: str = "1h", limit: int = 500,
                  venue: str | None = None, market_type: str = "spot", quote: str = "USDT"):
        asset = asset.upper()
        candidates = [venue] if venue is not None else \
            [v for v in venue_priority_for(asset) if v in self.providers]
        if not candidates:
            candidates = list(self.providers.keys())

        attempts = {}
        for v in candidates:
            provider = self.providers.get(v)
            if provider is None:
                attempts[v] = "no conectado para este usuario"
                continue
            try:
                return provider.get_ohlcv(asset, timeframe, limit, market_type=market_type, quote=quote)
            except Exception as e:
                log.info("Venue %s (ohlcv) falló para %s: %s", v, asset, e)
                attempts[v] = str(e)

        raise NoVenueAvailableError(asset, attempts)

    def clear_cache(self):
        self._cache.clear()
