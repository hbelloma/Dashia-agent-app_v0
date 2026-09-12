"""
test_router.py
===============
"""
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from market_data.router import UnifiedMarketData, NoVenueAvailableError
from market_data.models import PriceQuote


class FakeProvider:
    def __init__(self, venue_name, price=None, fail=False, fail_ohlcv=False):
        self.venue_name = venue_name
        self.price = price
        self.fail = fail
        self.fail_ohlcv = fail_ohlcv
        self.price_calls = 0
        self.ohlcv_calls = 0

    def get_price(self, asset, market_type="spot", quote="USDT"):
        self.price_calls += 1
        if self.fail:
            raise RuntimeError(f"{self.venue_name} no tiene {asset}/{quote}")
        return PriceQuote.now(asset, self.venue_name, self.price, f"{asset}/{quote}")

    def get_ohlcv(self, asset, timeframe="1h", limit=500, market_type="spot", quote="USDT"):
        self.ohlcv_calls += 1
        if self.fail_ohlcv:
            raise RuntimeError(f"{self.venue_name} sin OHLCV para {asset}")
        return [{"asset": asset, "venue": self.venue_name}]  # placeholder simple, no hace falta un DF real acá


def test_get_price_from_single_available_venue():
    umd = UnifiedMarketData({"binance": FakeProvider("binance", price=61000.0)})
    quote = umd.get_price("BTC")
    assert quote.price == 61000.0
    assert quote.venue == "binance"


def test_falls_back_to_second_venue_when_first_fails():
    binance = FakeProvider("binance", fail=True)
    bybit = FakeProvider("bybit", price=61050.0)
    umd = UnifiedMarketData({"binance": binance, "bybit": bybit})
    quote = umd.get_price("BTC")  # prioridad BTC: binance, bybit, weex, solana
    assert quote.venue == "bybit"
    assert binance.price_calls == 1


def test_raises_with_all_attempts_when_every_venue_fails():
    umd = UnifiedMarketData({
        "binance": FakeProvider("binance", fail=True),
        "bybit": FakeProvider("bybit", fail=True),
    })
    with pytest.raises(NoVenueAvailableError) as exc_info:
        umd.get_price("BTC")
    assert "binance" in str(exc_info.value)
    assert "bybit" in str(exc_info.value)


def test_explicit_venue_skips_priority_order():
    binance = FakeProvider("binance", price=61000.0)
    bybit = FakeProvider("bybit", price=61999.0)
    umd = UnifiedMarketData({"binance": binance, "bybit": bybit})
    quote = umd.get_price("BTC", venue="bybit")
    assert quote.venue == "bybit"
    assert binance.price_calls == 0


def test_unconnected_venue_is_skipped_not_a_crash():
    # el usuario solo tiene bybit conectado — binance ni aparece en `providers`
    umd = UnifiedMarketData({"bybit": FakeProvider("bybit", price=61000.0)})
    quote = umd.get_price("BTC")
    assert quote.venue == "bybit"


def test_cache_avoids_repeated_calls_within_ttl():
    provider = FakeProvider("binance", price=61000.0)
    umd = UnifiedMarketData({"binance": provider}, cache_ttl_s=10)
    umd.get_price("BTC")
    umd.get_price("BTC")
    umd.get_price("BTC")
    assert provider.price_calls == 1  # las siguientes 2 vinieron del caché


def test_cache_expires_after_ttl():
    provider = FakeProvider("binance", price=61000.0)
    umd = UnifiedMarketData({"binance": provider}, cache_ttl_s=0.05)
    umd.get_price("BTC")
    time.sleep(0.08)
    umd.get_price("BTC")
    assert provider.price_calls == 2


def test_use_cache_false_bypasses_cache():
    provider = FakeProvider("binance", price=61000.0)
    umd = UnifiedMarketData({"binance": provider}, cache_ttl_s=30)
    umd.get_price("BTC", use_cache=False)
    umd.get_price("BTC", use_cache=False)
    assert provider.price_calls == 2


def test_ohlcv_also_falls_back_between_venues():
    binance = FakeProvider("binance", fail_ohlcv=True)
    bybit = FakeProvider("bybit")
    umd = UnifiedMarketData({"binance": binance, "bybit": bybit})
    result = umd.get_ohlcv("BTC")
    assert result[0]["venue"] == "bybit"


def test_sol_prefers_solana_venue_first():
    solana = FakeProvider("solana", price=148.0)
    binance = FakeProvider("binance", price=148.5)
    umd = UnifiedMarketData({"solana": solana, "binance": binance})
    quote = umd.get_price("SOL")
    assert quote.venue == "solana"
    assert binance.price_calls == 0


def test_asset_without_known_priority_tries_whatever_is_connected():
    umd = UnifiedMarketData({"bybit": FakeProvider("bybit", price=1.23)})
    quote = umd.get_price("SOMENEWCOIN")
    assert quote.venue == "bybit"
