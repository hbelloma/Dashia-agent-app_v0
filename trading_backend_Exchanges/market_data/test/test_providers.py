"""
test_providers.py
==================
Prueba que los adaptadores realmente delegan en los conectores ya
construidos, con el símbolo correcto — incluido el caso especial de
Weex en modo swap ("BTC/USDT:USDT", no "BTC/USDT").
"""
import os
import sys
from unittest.mock import MagicMock
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from market_data.providers import CEXMarketDataProvider, SolanaMarketDataProvider, AssetNotSupportedError, OHLCVNotAvailableError


def test_cex_provider_get_price_uses_correct_symbol():
    fake_connector = MagicMock()
    fake_connector.get_last_price.return_value = 61000.0
    provider = CEXMarketDataProvider(fake_connector, "binance")

    quote = provider.get_price("BTC")
    fake_connector.get_last_price.assert_called_once_with("BTC/USDT")
    assert quote.price == 61000.0
    assert quote.venue == "binance"


def test_cex_provider_weex_swap_uses_colon_symbol_format():
    fake_connector = MagicMock()
    fake_connector.get_last_price.return_value = 61000.0
    provider = CEXMarketDataProvider(fake_connector, "weex")

    provider.get_price("BTC", market_type="swap")
    fake_connector.get_last_price.assert_called_once_with("BTC/USDT:USDT")


def test_cex_provider_spot_never_uses_colon_format_even_on_weex():
    fake_connector = MagicMock()
    fake_connector.get_last_price.return_value = 61000.0
    provider = CEXMarketDataProvider(fake_connector, "weex")

    provider.get_price("BTC", market_type="spot")
    fake_connector.get_last_price.assert_called_once_with("BTC/USDT")


def test_cex_provider_ohlcv_delegates_to_connector():
    fake_connector = MagicMock()
    fake_connector.get_ohlcv.return_value = "un-dataframe-cualquiera"
    provider = CEXMarketDataProvider(fake_connector, "bybit")

    result = provider.get_ohlcv("ETH", timeframe="4h", limit=200)
    fake_connector.get_ohlcv.assert_called_once_with("ETH/USDT", "4h", 200)
    assert result == "un-dataframe-cualquiera"


def test_solana_provider_computes_price_from_quote():
    fake_jupiter = MagicMock()
    fake_jupiter.resolve_mint_by_symbol.side_effect = lambda s: f"MINT_{s}"
    fake_jupiter.get_quote.return_value = {"outAmount": "500000"}  # 10 USDC -> 0.5 SOL (unidades atómicas simplificadas)

    provider = SolanaMarketDataProvider(fake_jupiter)
    quote = provider.get_price("SOL")
    assert quote.venue == "solana"
    assert quote.price > 0


def test_solana_provider_rejects_known_illiquid_assets():
    fake_jupiter = MagicMock()
    provider = SolanaMarketDataProvider(fake_jupiter)
    with pytest.raises(AssetNotSupportedError):
        provider.get_price("XRP")
    fake_jupiter.get_quote.assert_not_called()  # ni siquiera intenta la red para algo que ya se sabe que no aplica


def test_solana_provider_ohlcv_always_raises_clear_not_available_error():
    provider = SolanaMarketDataProvider(MagicMock())
    with pytest.raises(OHLCVNotAvailableError):
        provider.get_ohlcv("SOL")


def test_solana_ohlcv_uses_birdeye_when_configured():
    fake_birdeye = MagicMock()
    fake_birdeye.get_ohlcv_base_quote.return_value = [
        {"o": 148.0, "h": 149.0, "l": 147.5, "c": 148.8, "v": 1000.0, "unixTime": 1700000000},
    ]
    fake_jupiter = MagicMock()
    fake_jupiter.resolve_mint_by_symbol.side_effect = lambda s: f"MINT_{s}"

    provider = SolanaMarketDataProvider(fake_jupiter, birdeye_client=fake_birdeye)
    df = provider.get_ohlcv("SOL", timeframe="1h", limit=10)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.iloc[0]["close"] == 148.8
    fake_birdeye.get_ohlcv_base_quote.assert_called_once()


def test_solana_ohlcv_falls_back_to_geckoterminal_when_birdeye_fails():
    fake_birdeye = MagicMock()
    fake_birdeye.get_ohlcv_base_quote.side_effect = RuntimeError("401 unauthorized")
    fake_gecko = MagicMock()
    fake_gecko.get_ohlcv_by_token.return_value = [
        [1700000000, 148.0, 149.0, 147.5, 148.8, 1000.0],
    ]
    fake_jupiter = MagicMock()
    fake_jupiter.resolve_mint_by_symbol.side_effect = lambda s: f"MINT_{s}"

    provider = SolanaMarketDataProvider(fake_jupiter, birdeye_client=fake_birdeye, geckoterminal_client=fake_gecko)
    df = provider.get_ohlcv("SOL", timeframe="1h", limit=10)
    assert df.iloc[0]["close"] == 148.8
    fake_gecko.get_ohlcv_by_token.assert_called_once()


def test_solana_ohlcv_raises_with_both_errors_when_both_fail():
    fake_birdeye = MagicMock()
    fake_birdeye.get_ohlcv_base_quote.side_effect = RuntimeError("birdeye caído")
    fake_gecko = MagicMock()
    fake_gecko.get_ohlcv_by_token.side_effect = RuntimeError("gecko rate limited")
    fake_jupiter = MagicMock()
    fake_jupiter.resolve_mint_by_symbol.side_effect = lambda s: f"MINT_{s}"

    provider = SolanaMarketDataProvider(fake_jupiter, birdeye_client=fake_birdeye, geckoterminal_client=fake_gecko)
    with pytest.raises(OHLCVNotAvailableError) as exc_info:
        provider.get_ohlcv("SOL")
    assert "birdeye" in str(exc_info.value) and "gecko" in str(exc_info.value)


def test_solana_ohlcv_rejects_illiquid_asset_before_any_network_call():
    fake_birdeye = MagicMock()
    provider = SolanaMarketDataProvider(MagicMock(), birdeye_client=fake_birdeye)
    with pytest.raises(AssetNotSupportedError):
        provider.get_ohlcv("XRP")
    fake_birdeye.get_ohlcv_base_quote.assert_not_called()


def test_solana_ohlcv_unsupported_timeframe_raises_clear_error():
    provider = SolanaMarketDataProvider(MagicMock(), birdeye_client=MagicMock())
    with pytest.raises(OHLCVNotAvailableError):
        provider.get_ohlcv("SOL", timeframe="7m")
