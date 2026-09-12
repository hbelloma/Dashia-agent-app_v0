"""
client.py
=========
Conector a Weex (spot y swap) usando ccxt.

Diferencia importante y honesta con binance_connector / bybit_connector:
NO se encontró (ni en el código fuente de ccxt para weex.py, ni por
búsqueda en la documentación pública de Weex) un endpoint para verificar
programáticamente si una API key tiene permiso de retiro habilitado.
`weex.py` en ccxt directamente declara `'withdraw': False` en sus
capacidades y no expone nada tipo `apiRestrictions` o `query-api`.

En vez de fingir una verificación que no existe (lo cual sería PEOR que
no tener nada — daría falsa confianza), `verify_trade_only()` de este
cliente siempre lanza `PermissionCheckUnavailable`, y ningún método de
trading funciona hasta que se confirma manualmente que se revisó la
key en el dashboard de Weex, vía `acknowledge_manual_trade_only_check()`.

Otra limitación real encontrada leyendo weex.py: el modo sandbox/demo de
Weex SOLO cubre mercados swap (no spot), y solo un subconjunto de
métodos (fetchBalance, createOrder, fetchPositions, fetchClosedOrders,
fetchCanceledOrders) — ver el comentario original en ccxt citado abajo.

No se pudo probar nada de esto contra la red real (sin salida a
api.weex.com desde este sandbox).
"""

from __future__ import annotations
import time
import logging
from typing import Literal, Optional

import ccxt
import pandas as pd

from .config import WeexCredentials

log = logging.getLogger("weex_connector")

MarketType = Literal["spot", "swap"]


class PermissionCheckUnavailable(RuntimeError):
    """Weex no expone una forma confirmada de verificar permisos por API. Ver README."""


class WeexConnector:
    def __init__(self, creds: WeexCredentials, market_type: MarketType = "spot"):
        self.market_type = market_type
        self.exchange = ccxt.weex({
            "apiKey": creds.api_key, "secret": creds.api_secret, "enableRateLimit": True,
        })
        self._trade_only_acknowledged = False
        if creds.testnet:
            self.exchange.set_sandbox_mode(True)
            log.warning(
                "WeexConnector en modo sandbox: ccxt/weex documenta que el demo trading "
                "SOLO cubre mercados swap, con un subconjunto limitado de métodos. No "
                "asumir que spot funciona igual en sandbox que en producción."
            )
        else:
            log.warning("WeexConnector iniciado en PRODUCCIÓN (%s) — dinero real", market_type)

    # ------------------------------------------------------------------
    def verify_trade_only(self):
        raise PermissionCheckUnavailable(
            "Weex no tiene (que se haya podido confirmar) un endpoint para verificar "
            "permisos de una API key. Hay que revisar MANUALMENTE en el dashboard de "
            "Weex que la key tenga marcado solo trading, sin retiro, y con whitelist "
            "de IP — y luego llamar a acknowledge_manual_trade_only_check(True)."
        )

    def acknowledge_manual_trade_only_check(self, confirmed_no_withdrawal: bool):
        """
        La app debe llamar esto SOLO después de que un humano confirmó,
        mirando el dashboard de Weex, que la key no tiene permiso de retiro.
        Sin esto, ningún método de trading de esta clase funciona.
        """
        if not confirmed_no_withdrawal:
            raise PermissionCheckUnavailable("confirmed_no_withdrawal debe ser True para operar")
        self._trade_only_acknowledged = True
        log.info("Verificación manual de 'solo trading' confirmada para esta sesión")

    def _require_manual_ack(self):
        if not self._trade_only_acknowledged:
            raise PermissionCheckUnavailable(
                "No se puede operar: llamar primero a "
                "acknowledge_manual_trade_only_check(True) tras confirmar manualmente "
                "en el dashboard de Weex que la key no tiene permiso de retiro."
            )

    # ------------------------------------------------------------------
    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        raw = self._with_retry(self.exchange.fetch_ohlcv, symbol, timeframe, None, limit)
        df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df.set_index("ts")

    def get_balance(self) -> dict:
        self._require_manual_ack()
        return self._with_retry(self.exchange.fetch_balance)

    def get_last_price(self, symbol: str) -> float:
        return float(self._with_retry(self.exchange.fetch_ticker, symbol)["last"])

    # ------------------------------------------------------------------
    def place_market_order(self, symbol: str, side: Literal["buy", "sell"], amount: float) -> dict:
        self._require_manual_ack()
        log.info("MARKET %s %s amount=%s", side.upper(), symbol, amount)
        return self._with_retry(self.exchange.create_order, symbol, "market", side, amount)

    def place_limit_order(self, symbol: str, side: Literal["buy", "sell"], amount: float, price: float) -> dict:
        self._require_manual_ack()
        return self._with_retry(self.exchange.create_order, symbol, "limit", side, amount, price)

    def place_stop_loss(self, symbol: str, side: Literal["buy", "sell"], amount: float, stop_price: float) -> dict:
        self._require_manual_ack()
        return self._with_retry(self.exchange.create_order, symbol, "market", side, amount,
                                 None, {"stopPrice": stop_price})

    def place_take_profit(self, symbol: str, side: Literal["buy", "sell"], amount: float, take_price: float) -> dict:
        self._require_manual_ack()
        return self._with_retry(self.exchange.create_order, symbol, "limit", side, amount, take_price)

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        self._require_manual_ack()
        return self._with_retry(self.exchange.cancel_order, order_id, symbol)

    def get_open_positions(self) -> list:
        self._require_manual_ack()
        if self.market_type != "swap":
            return []
        positions = self._with_retry(self.exchange.fetch_positions)
        return [p for p in positions if float(p.get("contracts") or 0) != 0]

    def close_position(self, symbol: str) -> Optional[dict]:
        for p in self.get_open_positions():
            if p["symbol"] == symbol:
                side = "sell" if p["side"] == "long" else "buy"
                return self.place_market_order(symbol, side, abs(float(p["contracts"])))
        return None

    # ------------------------------------------------------------------
    def _with_retry(self, fn, *args, max_retries: int = 3, backoff: float = 1.5, **kwargs):
        last_exc = None
        for attempt in range(max_retries):
            try:
                return fn(*args, **kwargs)
            except ccxt.NetworkError as e:
                last_exc = e
                log.warning("NetworkError (intento %d/%d): %s", attempt + 1, max_retries, e)
                time.sleep(backoff ** attempt)
            except (ccxt.InsufficientFunds, ccxt.InvalidOrder):
                raise
            except ccxt.ExchangeError as e:
                log.error("ExchangeError: %s", e)
                raise
        raise last_exc
