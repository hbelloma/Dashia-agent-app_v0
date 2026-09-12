"""
client.py
=========
Conector real a Binance (spot y futuros) usando ccxt. Este código NO se
pudo probar contra la red real de Binance desde este entorno (sandbox
sin salida a api.binance.com — ver README), pero sigue exactamente los
métodos documentados y estables de ccxt 4.x. Antes de usarlo con fondos
reales: correr primero en testnet (por defecto) y revisar los tests en
tests/test_client.py.
"""

from __future__ import annotations
import time
import logging
from dataclasses import dataclass
from typing import Literal, Optional

import ccxt
import pandas as pd

from .config import BinanceCredentials

log = logging.getLogger("binance_connector")

MarketType = Literal["spot", "future"]


class TradeOnlyViolation(RuntimeError):
    """Se lanza si la API key tiene permiso de retiro habilitado."""


class BinanceConnector:
    def __init__(self, creds: BinanceCredentials, market_type: MarketType = "spot"):
        self.market_type = market_type
        klass = ccxt.binance if market_type == "spot" else ccxt.binanceusdm
        self.exchange = klass({
            "apiKey": creds.api_key,
            "secret": creds.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": market_type, "adjustForTimeDifference": True},
        })
        if creds.testnet:
            self.exchange.set_sandbox_mode(True)
            log.info("BinanceConnector iniciado en TESTNET (%s)", market_type)
        else:
            log.warning("BinanceConnector iniciado en PRODUCCIÓN (%s) — dinero real", market_type)

    # ------------------------------------------------------------------
    # Seguridad: nunca operar con una key que tenga permiso de retiro
    # ------------------------------------------------------------------
    def verify_trade_only(self) -> dict:
        """
        Confirma que la API key NO tiene permiso de retiro habilitado.
        Lanza TradeOnlyViolation si lo tiene — la app debe rechazar la
        key en el momento de vincularla (blueprint §2).
        """
        if self.market_type != "spot":
            log.warning("verify_trade_only solo consulta el endpoint de spot; "
                        "verifica también los permisos de la cuenta de futuros en el dashboard de Binance.")
        try:
            restrictions = self.exchange.sapiGetAccountApiRestrictions()
        except Exception as e:
            raise RuntimeError(f"No se pudo consultar apiRestrictions: {e}") from e

        if restrictions.get("enableWithdrawals"):
            raise TradeOnlyViolation(
                "Esta API key tiene retiros habilitados. Créala de nuevo en Binance "
                "con SOLO 'Enable Spot & Margin Trading' / 'Enable Futures', sin "
                "'Enable Withdrawals', y con whitelist de IP activada."
            )
        return restrictions

    # ------------------------------------------------------------------
    # Datos de mercado
    # ------------------------------------------------------------------
    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        """
        Devuelve un DataFrame con columnas open/high/low/close/volume,
        indexado por timestamp — mismo formato que espera dashia_engine.
        """
        raw = self._with_retry(self.exchange.fetch_ohlcv, symbol, timeframe, None, limit)
        df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df.set_index("ts")

    def get_balance(self) -> dict:
        return self._with_retry(self.exchange.fetch_balance)

    def get_last_price(self, symbol: str) -> float:
        ticker = self._with_retry(self.exchange.fetch_ticker, symbol)
        return float(ticker["last"])

    # ------------------------------------------------------------------
    # Órdenes
    # ------------------------------------------------------------------
    def place_market_order(self, symbol: str, side: Literal["buy", "sell"], amount: float) -> dict:
        log.info("MARKET %s %s amount=%s", side.upper(), symbol, amount)
        return self._with_retry(self.exchange.create_order, symbol, "market", side, amount)

    def place_limit_order(self, symbol: str, side: Literal["buy", "sell"], amount: float, price: float) -> dict:
        log.info("LIMIT %s %s amount=%s price=%s", side.upper(), symbol, amount, price)
        return self._with_retry(self.exchange.create_order, symbol, "limit", side, amount, price)

    def place_stop_loss(self, symbol: str, side: Literal["buy", "sell"], amount: float, stop_price: float) -> dict:
        """side = lado de CIERRE (si estás long, side='sell')."""
        params = {"stopPrice": stop_price}
        order_type = "STOP_MARKET" if self.market_type == "future" else "stop_loss_limit"
        if self.market_type == "spot":
            params["price"] = stop_price  # ccxt spot exige price límite junto al stop
        return self._with_retry(self.exchange.create_order, symbol, order_type, side, amount, None, params)

    def place_take_profit(self, symbol: str, side: Literal["buy", "sell"], amount: float, take_price: float) -> dict:
        params = {"stopPrice": take_price}
        order_type = "TAKE_PROFIT_MARKET" if self.market_type == "future" else "limit"
        price = None if self.market_type == "future" else take_price
        return self._with_retry(self.exchange.create_order, symbol, order_type, side, amount, price, params)

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        return self._with_retry(self.exchange.cancel_order, order_id, symbol)

    def cancel_all_open_orders(self, symbol: str) -> list:
        return self._with_retry(self.exchange.cancel_all_orders, symbol)

    # ------------------------------------------------------------------
    # Futuros
    # ------------------------------------------------------------------
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
            except ccxt.InsufficientFunds:
                raise
            except ccxt.InvalidOrder:
                raise
            except ccxt.ExchangeError as e:
                last_exc = e
                log.error("ExchangeError: %s", e)
                raise
        raise last_exc
