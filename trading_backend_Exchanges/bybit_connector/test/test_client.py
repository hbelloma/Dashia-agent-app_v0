"""
test_client.py
===============
Igual que en binance_connector: ccxt mockeado, valida lógica propia sin red.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bybit_connector.config import BybitCredentials
from bybit_connector.client import BybitConnector, TradeOnlyViolation


def _fake_creds():
    return BybitCredentials(api_key="x", api_secret="y", testnet=True)


@patch("bybit_connector.client.ccxt.bybit")
def test_ohlcv_returns_dataframe_with_expected_columns(mock_bybit_cls):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ohlcv.return_value = [
        [1700000000000, 100.0, 105.0, 98.0, 103.0, 12.5],
        [1700003600000, 103.0, 108.0, 101.0, 106.0, 9.1],
    ]
    mock_bybit_cls.return_value = mock_exchange

    conn = BybitConnector(_fake_creds(), market_type="spot")
    df = conn.get_ohlcv("BTC/USDT", "1h", 2)

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 2


@patch("bybit_connector.client.ccxt.bybit")
def test_verify_trade_only_raises_when_withdraw_permission_present(mock_bybit_cls):
    mock_exchange = MagicMock()
    mock_exchange.privateGetV5UserQueryApi.return_value = {
        "result": {"permissions": {"Wallet": ["Withdraw", "AccountTransfer"], "Spot": ["SpotTrade"]}}
    }
    mock_bybit_cls.return_value = mock_exchange

    conn = BybitConnector(_fake_creds(), market_type="spot")
    try:
        conn.verify_trade_only()
        assert False, "debió lanzar TradeOnlyViolation"
    except TradeOnlyViolation:
        pass


@patch("bybit_connector.client.ccxt.bybit")
def test_verify_trade_only_passes_when_no_withdraw_permission(mock_bybit_cls):
    mock_exchange = MagicMock()
    mock_exchange.privateGetV5UserQueryApi.return_value = {
        "result": {"permissions": {"Wallet": ["AccountTransfer"], "Spot": ["SpotTrade"]}}
    }
    mock_bybit_cls.return_value = mock_exchange

    conn = BybitConnector(_fake_creds(), market_type="spot")
    result = conn.verify_trade_only()
    assert "Withdraw" not in result["permissions"]["Wallet"]


@patch("bybit_connector.client.ccxt.bybit")
def test_market_type_future_sets_linear_suboption(mock_bybit_cls):
    mock_exchange = MagicMock()
    mock_bybit_cls.return_value = mock_exchange

    BybitConnector(_fake_creds(), market_type="future")
    args, kwargs = mock_bybit_cls.call_args
    call_config = args[0]
    assert call_config["options"]["defaultType"] == "swap"
    assert call_config["options"]["defaultSubType"] == "linear"


@patch("bybit_connector.client.ccxt.bybit")
def test_place_market_order_calls_create_order_correctly(mock_bybit_cls):
    mock_exchange = MagicMock()
    mock_exchange.create_order.return_value = {"id": "bybit-order-1"}
    mock_bybit_cls.return_value = mock_exchange

    conn = BybitConnector(_fake_creds(), market_type="spot")
    result = conn.place_market_order("BTC/USDT", "buy", 0.01)

    mock_exchange.create_order.assert_called_once_with("BTC/USDT", "market", "buy", 0.01)
    assert result["id"] == "bybit-order-1"
