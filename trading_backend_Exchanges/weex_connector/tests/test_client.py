"""
test_client.py
===============
Lo más importante de probar acá: que NINGÚN método de trading funciona
sin el reconocimiento manual explícito — no es un detalle decorativo.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from weex_connector.config import WeexCredentials
from weex_connector.client import WeexConnector, PermissionCheckUnavailable


def _fake_creds():
    return WeexCredentials(api_key="x", api_secret="y", testnet=True)


@patch("weex_connector.client.ccxt.weex")
def test_verify_trade_only_always_raises_not_implemented_style(mock_weex_cls):
    mock_weex_cls.return_value = MagicMock()
    conn = WeexConnector(_fake_creds())
    try:
        conn.verify_trade_only()
        assert False, "verify_trade_only() debe rechazar siempre en Weex — no hay endpoint confirmado"
    except PermissionCheckUnavailable:
        pass


@patch("weex_connector.client.ccxt.weex")
def test_trading_blocked_without_manual_acknowledgment(mock_weex_cls):
    mock_weex_cls.return_value = MagicMock()
    conn = WeexConnector(_fake_creds())
    try:
        conn.place_market_order("BTC/USDT", "buy", 0.01)
        assert False, "no debería poder operar sin el ack manual"
    except PermissionCheckUnavailable:
        pass


@patch("weex_connector.client.ccxt.weex")
def test_trading_works_after_manual_acknowledgment(mock_weex_cls):
    mock_exchange = MagicMock()
    mock_exchange.create_order.return_value = {"id": "weex-order-1"}
    mock_weex_cls.return_value = mock_exchange

    conn = WeexConnector(_fake_creds())
    conn.acknowledge_manual_trade_only_check(True)
    result = conn.place_market_order("BTC/USDT", "buy", 0.01)
    assert result["id"] == "weex-order-1"


@patch("weex_connector.client.ccxt.weex")
def test_acknowledgment_with_false_still_blocks(mock_weex_cls):
    mock_weex_cls.return_value = MagicMock()
    conn = WeexConnector(_fake_creds())
    try:
        conn.acknowledge_manual_trade_only_check(False)
        assert False
    except PermissionCheckUnavailable:
        pass
    try:
        conn.place_market_order("BTC/USDT", "buy", 0.01)
        assert False
    except PermissionCheckUnavailable:
        pass


@patch("weex_connector.client.ccxt.weex")
def test_get_last_price_does_not_require_acknowledgment(mock_weex_cls):
    # leer precio de mercado es de solo lectura, no necesita el ack de trading
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 61000.0}
    mock_weex_cls.return_value = mock_exchange

    conn = WeexConnector(_fake_creds())
    assert conn.get_last_price("BTC/USDT") == 61000.0
