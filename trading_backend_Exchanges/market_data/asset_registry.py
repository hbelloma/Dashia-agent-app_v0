"""
asset_registry.py
==================
La parte que hace posible pedir "BTC" sin saber de qué exchange viene:
traduce un activo genérico al símbolo exacto que cada venue espera, y
define un orden de prioridad razonable de dónde buscarlo primero.

Importante ser honesto sobre el límite de esto: la tabla de prioridad de
abajo es un punto de partida razonable, NO una verificación de que cada
exchange realmente lista cada par — este sandbox no tiene salida de red
para confirmarlo contra los mercados reales de cada exchange. En
producción, `UnifiedMarketData` (ver router.py) resuelve esto en la
práctica probando el venue y pasando al siguiente si falla — no depende
de que esta tabla sea perfecta, solo de que sea un buen orden de intento.
"""

from __future__ import annotations
from dataclasses import dataclass, field

# Activos que la app soporta explícitamente (ver el pedido original:
# BTC, ETH, SOL, LTC, XRP, ARB, XAU + memecoins)
KNOWN_ASSETS = {"BTC", "ETH", "SOL", "LTC", "XRP", "ARB", "XAU", "WIF", "BONK"}

# Orden de prioridad por defecto — dónde intentar primero. Ver nota
# arriba: esto es un punto de partida, no una garantía de listado.
DEFAULT_VENUE_PRIORITY = {
    "BTC": ["binance", "bybit", "weex", "solana"],
    "ETH": ["binance", "bybit", "weex", "solana"],
    "SOL": ["solana", "binance", "bybit", "weex"],
    "LTC": ["binance", "bybit", "weex"],
    "XRP": ["binance", "bybit", "weex"],
    "ARB": ["binance", "bybit", "weex"],
    "XAU": ["binance"],  # no confirmado en más venues — ver README
    "WIF": ["solana", "binance", "bybit"],
    "BONK": ["solana"],
}

# Activos que casi seguro NO tienen una versión líquida en Solana (ver
# solana_connector/README.md — misma conclusión, reforzada acá).
NOT_LIQUID_ON_SOLANA = {"LTC", "XRP", "XAU"}


def cex_symbol(asset: str, quote: str = "USDT", market_type: str = "spot", venue: str = "") -> str:
    """
    Formato unificado de ccxt para spot y la mayoría de swaps: "BTC/USDT".
    Weex en modo swap usa "BTC/USDT:USDT" (símbolo liquidado en USDT) —
    ver weex_connector/README.md sobre esta convención.
    """
    if venue == "weex" and market_type == "swap":
        return f"{asset}/{quote}:{quote}"
    return f"{asset}/{quote}"


def venue_priority_for(asset: str) -> list[str]:
    asset = asset.upper()
    return list(DEFAULT_VENUE_PRIORITY.get(asset, ["binance", "bybit", "weex"]))


@dataclass
class AssetQuery:
    asset: str
    venue: str | None = None       # si se pide un venue específico, se salta el orden de prioridad
    market_type: str = "spot"
    quote: str = "USDT"            # USDT para CEX; el proveedor de Solana ignora esto y usa USDC internamente
