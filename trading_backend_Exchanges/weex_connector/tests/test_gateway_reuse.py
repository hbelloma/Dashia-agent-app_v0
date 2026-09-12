"""
test_gateway_reuse.py
=======================
Mismo gateway reutilizado, pero acá además importa confirmar que el
bloqueo de "sin verificación manual" se respeta INCLUSO cuando la orden
viene del gateway (y no de una llamada directa al conector) — el
gateway no puede saltarse esa barrera.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from weex_connector.config import WeexCredentials
from weex_connector.client import WeexConnector, PermissionCheckUnavailable
from binance_connector.gateway import TradingGateway
from binance_connector.config import GatewayLimits


@patch("weex_connector.client.ccxt.weex")
def test_gateway_order_blocked_without_manual_ack_even_via_gateway(mock_weex_cls):
    mock_weex_cls.return_value = MagicMock()
    conn = WeexConnector(WeexCredentials(api_key="x", api_secret="y"))
    limits = GatewayLimits(allowed_symbols=("BTC/USDT",))
    gateway = TradingGateway(conn, limits, risk_cfg=None, audit_log_path="/tmp/weex_reuse_audit.jsonl")

    try:
        gateway.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=500)
        assert False, "el gateway no debería poder saltarse el bloqueo del conector"
    except PermissionCheckUnavailable:
        pass


@patch("weex_connector.client.ccxt.weex")
def test_gateway_order_works_after_manual_ack(mock_weex_cls):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 100.0}
    mock_exchange.create_order.return_value = {"id": "weex-order-2"}
    mock_weex_cls.return_value = mock_exchange

    conn = WeexConnector(WeexCredentials(api_key="x", api_secret="y"))
    conn.acknowledge_manual_trade_only_check(True)
    limits = GatewayLimits(allowed_symbols=("BTC/USDT",))
    gateway = TradingGateway(conn, limits, risk_cfg=None, audit_log_path="/tmp/weex_reuse_audit2.jsonl")

    result = gateway.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=500)
    assert result["id"] == "weex-order-2"
