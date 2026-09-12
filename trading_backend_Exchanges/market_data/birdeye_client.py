"""
birdeye_client.py
==================
Cliente de los endpoints de OHLCV de Birdeye — verificados contra su
documentación pública (docs.birdeye.so) en septiembre 2026:

  - GET /defi/ohlcv/base_quote?base_address=...&quote_address=...&type=...
  - GET /defi/history_price?address=...&type=...

Requiere API key (header X-API-KEY) incluso en el plan gratis. El plan
gratis da 30K compute units/mes a 1 req/seg. La granularidad más fina en
tiempo real (velas de 1s/15s/30s) existe pero solo vía WebSocket, que
requiere el plan Business de pago — no está implementada acá.

No se pudo probar contra la red real desde este sandbox (sin salida a
public-api.birdeye.so).
"""

from __future__ import annotations
import logging
import requests

log = logging.getLogger("market_data.birdeye")

BASE_URL = "https://public-api.birdeye.so"


class BirdeyeAPIError(RuntimeError):
    pass


class BirdeyeClient:
    def __init__(self, api_key: str, chain: str = "solana", timeout: float = 10.0):
        self.api_key = api_key
        self.chain = chain
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"accept": "application/json", "x-chain": self.chain, "X-API-KEY": self.api_key}

    def get_ohlcv_base_quote(self, base_address: str, quote_address: str,
                              timeframe: str, time_from: int, time_to: int) -> list[dict]:
        """timeframe en formato Birdeye: '1m','5m','15m','1H','4H','1D', etc."""
        params = {"base_address": base_address, "quote_address": quote_address,
                   "type": timeframe, "time_from": time_from, "time_to": time_to}
        resp = requests.get(f"{BASE_URL}/defi/ohlcv/base_quote", params=params,
                             headers=self._headers(), timeout=self.timeout)
        if resp.status_code != 200:
            raise BirdeyeAPIError(f"ohlcv/base_quote falló ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        if not data.get("success"):
            raise BirdeyeAPIError(f"Birdeye devolvió success=false: {data}")
        return data["data"]["items"]

    def get_latest_price(self, address: str) -> float:
        """Vía history_price, tomando el punto más reciente — Birdeye no separa
        un endpoint de 'solo el precio actual' distinto en la API pública."""
        import time
        now = int(time.time())
        params = {"address": address, "address_type": "token", "type": "1m",
                   "time_from": now - 300, "time_to": now}
        resp = requests.get(f"{BASE_URL}/defi/history_price", params=params,
                             headers=self._headers(), timeout=self.timeout)
        if resp.status_code != 200:
            raise BirdeyeAPIError(f"history_price falló ({resp.status_code}): {resp.text[:300]}")
        items = resp.json()["data"]["items"]
        if not items:
            raise BirdeyeAPIError(f"Sin datos de precio recientes para {address}")
        return float(items[-1]["value"])
