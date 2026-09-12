"""
client.py
=========
Conector real a Bybit (spot y futuros linear/USDT) usando ccxt.

A diferencia de Binance, esto NO se pudo verificar ni siquiera con una
suposición razonable "a ojo" — se confirmó cada detalle contra el código
fuente de ccxt instalado en este entorno (no contra la documentación de
Bybit directamente, que no se pudo alcanzar por red, pero ccxt SÍ está
instalado localmente y se pudo inspeccionar de verdad):

  - El endpoint de permisos es `v5/user/query-api`, y ccxt lo expone
    como `exchange.privateGetV5UserQueryApi()` — confirmado corriendo
    `hasattr()` sobre una instancia real de ccxt.bybit.
  - `options.defaultType` acepta 'spot'/'swap'/'future'/'option', y
    `defaultSubType` 'linear'/'inverse' — confirmado leyendo bybit.py.
  - El testnet se activa con `set_sandbox_mode(True)` (URLs de testnet
    ya están definidas en el propio bybit.py de ccxt).

Igual que binance_connector: no se probó contra la red real de Bybit
desde este sandbox (sin salida a api.bybit.com).
"""

from __future__ import annotations
import time
import logging
from typing import Literal, Optional

import ccxt
import pandas as pd

from .config import BybitCredentials

log = logging.getLogger("bybit_connector")

MarketType = Literal["spot", "future"]


class TradeOnlyViolation(RuntimeError):
    pass


class BybitConnector:
    def __init__(self, creds: BybitCredentials, market_type: MarketType = "spot"):
        self.market_type = market_type
        options = {"defaultType": "spot" if market_type == "spot" else "swap",
                   "adjustForTimeDifference": True}
        if market_type == "future":
            options["defaultSubType"] = "linear"  # USDT perpetual — lo que la mayoría llama "futuros"
        self.exchange = ccxt.bybit({
            "apiKey": creds.api_key, "secret": creds.api_secret,
            "enableRateLimit": True, "options": options,
        })
        if creds.testnet:
            self.exchange.set_sandbox_mode(True)
            log.info("BybitConnector iniciado en TESTNET (%s)", market_type)
        else:
            log.warning("BybitConnector iniciado en PRODUCCIÓN (%s) — dinero real", market_type)

    # ------------------------------------------------------------------
    def verify_trade_only(self) -> dict:
        """
        Confirma que la API key NO tiene permiso de retiro.
        Ver permissions.Wallet en la respuesta — "Withdraw" solo aparece
        ahí si el permiso de retiro está habilitado (y solo aplica a la
        cuenta master, según la documentación de Bybit).
        """
        try:
            resp = self.exchange.privateGetV5UserQueryApi()
        except Exception as e:
            raise RuntimeError(f"No se pudo consultar v5/user/query-api: {e}") from e

        result = resp.get("result", {})
        wallet_perms = result.get("permissions", {}).get("Wallet", [])
        if "Withdraw" in wallet_perms:
            raise TradeOnlyViolation(
                "Esta API key tiene permiso de retiro (Withdraw) habilitado. "
                "Créala de nuevo en Bybit marcando solo 'Contract Trade' y/o "
                "'Spot Trade', sin 'Withdrawal', y con whitelist de IP activada."
            )
        trade_perms = result.get("permissions", {}).get("ContractTrade", []) + \
                      result.get("permissions", {}).get("Spot", [])
        if not trade_perms:
            log.warning("La key no muestra permisos de trading activos — revisar en el dashboard de Bybit")
        return result

    # ------------------------------------------------------------------
    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        raw = self._with_retry(self.exchange.fetch_ohlcv, symbol, timeframe, None, limit)
        df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df.set_index("ts")

    def get_balance(self) -> dict:
        return self._with_retry(self.exchange.fetch_balance)

    def get_last_price(self, symbol: str) -> float:
        return float(self._with_retry(self.exchange.fetch_ticker, symbol)["last"])

    # ------------------------------------------------------------------
    def place_market_order(self, symbol: str, side: Literal["buy", "sell"], amount: float) -> dict:
        log.info("MARKET %s %s amount=%s", side.upper(), symbol, amount)
        return self._with_retry(self.exchange.create_order, symbol, "market", side, amount)

    def place_limit_order(self, symbol: str, side: Literal["buy", "sell"], amount: float, price: float) -> dict:
        return self._with_retry(self.exchange.create_order, symbol, "limit", side, amount, price)

    def place_stop_loss(self, symbol: str, side: Literal["buy", "sell"], amount: float, stop_price: float) -> dict:
        params = {"stopLoss": stop_price} if self.market_type == "future" else {"stopPrice": stop_price}
        order_type = "market" if self.market_type == "future" else "stop_loss_limit"
        price = None if self.market_type == "future" else stop_price
        return self._with_retry(self.exchange.create_order, symbol, order_type, side, amount, price, params)

    def place_take_profit(self, symbol: str, side: Literal["buy", "sell"], amount: float, take_price: float) -> dict:
        params = {"takeProfit": take_price} if self.market_type == "future" else {}
        order_type = "market" if self.market_type == "future" else "limit"
        price = None if self.market_type == "future" else take_price
        return self._with_retry(self.exchange.create_order, symbol, order_type, side, amount, price, params)

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        return self._with_retry(self.exchange.cancel_order, order_id, symbol)

    def cancel_all_open_orders(self, symbol: str) -> list:
        return self._with_retry(self.exchange.cancel_all_orders, symbol)

    def get_open_positions(self) -> list:
        if self.market_type != "future":
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
