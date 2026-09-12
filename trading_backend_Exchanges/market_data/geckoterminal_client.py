"""
geckoterminal_client.py
=========================
Cliente del endpoint de OHLCV de GeckoTerminal (producto on-chain de
CoinGecko) — verificado contra su documentación pública en septiembre
2026:

  GET /api/v2/networks/{network}/tokens/{token_address}/ohlcv/{timeframe}

Lo más práctico de este endpoint: se pide por DIRECCIÓN DE TOKEN
directo (no hace falta encontrar primero la dirección del pool) — usa
automáticamente el pool más líquido de ese token. Encaja directo con
`resolve_mint_by_symbol()` de jupiter_client.py, sin pasos intermedios.

Gratis, sin API key para el uso básico ("Keyless Public API"), 30
llamadas/minuto. La granularidad de 1s/15s/30s existe pero es exclusiva
del plan Pro de pago — acá solo se implementa day/hour/minute.

No se pudo probar contra la red real desde este sandbox (sin salida a
api.geckoterminal.com).
"""

from __future__ import annotations
import logging
import requests

log = logging.getLogger("market_data.geckoterminal")

BASE_URL = "https://api.geckoterminal.com/api/v2"


class GeckoTerminalAPIError(RuntimeError):
    pass


class GeckoTerminalClient:
    def __init__(self, network: str = "solana", timeout: float = 10.0):
        self.network = network
        self.timeout = timeout

    def get_ohlcv_by_token(self, token_address: str, timeframe: str = "hour",
                            aggregate: int = 1, limit: int = 100, currency: str = "usd") -> list[list]:
        """
        timeframe: 'day' | 'hour' | 'minute'. Devuelve una lista de
        [unix_timestamp, open, high, low, close, volume] — formato nativo
        de GeckoTerminal (lista de arrays, no de objetos).
        """
        url = f"{BASE_URL}/networks/{self.network}/tokens/{token_address}/ohlcv/{timeframe}"
        params = {"aggregate": aggregate, "limit": limit, "currency": currency, "token": "base"}
        resp = requests.get(url, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise GeckoTerminalAPIError(f"ohlcv falló ({resp.status_code}): {resp.text[:300]}")
        try:
            return resp.json()["data"]["attributes"]["ohlcv_list"]
        except (KeyError, TypeError) as e:
            raise GeckoTerminalAPIError(f"Respuesta inesperada de GeckoTerminal: {e}") from e
