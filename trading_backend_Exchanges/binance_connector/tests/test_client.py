"""
test_client.py
===============
El objeto ccxt.binance real se reemplaza por un mock — así se valida la
lógica propia (formateo de OHLCV a DataFrame, detección de permiso de
retiro) sin necesitar red hacia Binance, que este sandbox no tiene.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from binance_connector.config import BinanceCredentials
from binance_connector.client import BinanceConnector, TradeOnlyViolation


def _fake_creds():
    return BinanceCredentials(api_key="x", api_secret="y", testnet=True)


@patch("binance_connector.client.ccxt.binance")
def test_ohlcv_returns_dataframe_with_expected_columns(mock_binance_cls):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ohlcv.return_value = [
        [1700000000000, 100.0, 105.0, 98.0, 103.0, 12.5],
        [1700003600000, 103.0, 108.0, 101.0, 106.0, 9.1],
    ]
    mock_binance_cls.return_value = mock_exchange

    conn = BinanceConnector(_fake_creds(), market_type="spot")
    df = conn.get_ohlcv("BTC/USDT", "1h", 2)

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df.iloc[0]["close"] == 103.0


@patch("binance_connector.client.ccxt.binance")
def test_verify_trade_only_raises_when_withdrawals_enabled(mock_binance_cls):
    mock_exchange = MagicMock()
    mock_exchange.sapiGetAccountApiRestrictions.return_value = {"enableWithdrawals": True}
    mock_binance_cls.return_value = mock_exchange

    conn = BinanceConnector(_fake_creds(), market_type="spot")
    try:
        conn.verify_trade_only()
        assert False, "debió lanzar TradeOnlyViolation"
    except TradeOnlyViolation:
        pass


@patch("binance_connector.client.ccxt.binance")
def test_verify_trade_only_passes_when_withdrawals_disabled(mock_binance_cls):
    mock_exchange = MagicMock()
    mock_exchange.sapiGetAccountApiRestrictions.return_value = {"enableWithdrawals": False}
    mock_binance_cls.return_value = mock_exchange

    conn = BinanceConnector(_fake_creds(), market_type="spot")
    result = conn.verify_trade_only()
    assert result["enableWithdrawals"] is False


@patch("binance_connector.client.ccxt.binance")
def test_place_market_order_calls_create_order_correctly(mock_binance_cls):
    mock_exchange = MagicMock()
    mock_exchange.create_order.return_value = {"id": "abc123"}
    mock_binance_cls.return_value = mock_exchange

    conn = BinanceConnector(_fake_creds(), market_type="spot")
    result = conn.place_market_order("BTC/USDT", "buy", 0.01)

    mock_exchange.create_order.assert_called_once_with("BTC/USDT", "market", "buy", 0.01)
    assert result["id"] == "abc123"
