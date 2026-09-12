"""
test_gateway_reuse.py
=======================
No se duplicó gateway.py para Bybit — se reutiliza
binance_connector.gateway.TradingGateway tal cual, porque BybitConnector
implementa los mismos métodos (get_last_price, place_market_order,
place_stop_loss, place_take_profit). Este test prueba que esa reutilización
funciona de verdad, no solo que "debería" por duck typing.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bybit_connector.config import BybitCredentials
from bybit_connector.client import BybitConnector
from binance_connector.gateway import TradingGateway, GatewayRejection
from binance_connector.config import GatewayLimits


@patch("bybit_connector.client.ccxt.bybit")
def test_binance_gateway_works_unmodified_with_bybit_connector(mock_bybit_cls):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 100.0}
    mock_exchange.create_order.return_value = {"id": "order-1"}
    mock_bybit_cls.return_value = mock_exchange

    conn = BybitConnector(BybitCredentials(api_key="x", api_secret="y"), market_type="spot")
    limits = GatewayLimits(max_position_usd=1000, max_daily_loss_usd=100,
                            max_orders_per_minute=5, allowed_symbols=("BTC/USDT",))
    gateway = TradingGateway(conn, limits, risk_cfg=None, audit_log_path="/tmp/bybit_reuse_audit.jsonl")

    result = gateway.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=500)
    assert result["id"] == "order-1"
    mock_exchange.create_order.assert_called_once()


@patch("bybit_connector.client.ccxt.bybit")
def test_gateway_symbol_whitelist_still_applies_to_bybit(mock_bybit_cls):
    mock_bybit_cls.return_value = MagicMock()
    conn = BybitConnector(BybitCredentials(api_key="x", api_secret="y"), market_type="spot")
    limits = GatewayLimits(allowed_symbols=("ETH/USDT",))  # BTC no está permitido
    gateway = TradingGateway(conn, limits, risk_cfg=None, audit_log_path="/tmp/bybit_reuse_audit2.jsonl")

    try:
        gateway.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=500)
        assert False, "debió rechazar el símbolo"
    except GatewayRejection:
        pass
