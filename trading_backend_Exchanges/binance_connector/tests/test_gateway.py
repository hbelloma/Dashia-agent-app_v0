"""
test_gateway.py
================
Estos tests NO tocan la red — usan un conector falso (FakeConnector) para
validar que la lógica de límites del gateway funciona de verdad. Esta es
la parte más importante de auditar antes de conectar dinero real, y es
la única parte de todo el proyecto que se pudo probar de punta a punta
dentro de este sandbox (sin salida a internet hacia Binance).
"""
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from binance_connector.config import GatewayLimits
from binance_connector.gateway import TradingGateway, GatewayRejection, CircuitBreakerTripped


class FakeConnector:
    """Sustituye a BinanceConnector en los tests: no llama a ninguna red."""
    def __init__(self, price=100.0):
        self.price = price
        self.orders = []

    def get_last_price(self, symbol):
        return self.price

    def place_market_order(self, symbol, side, amount):
        order = {"id": f"fake-{len(self.orders)}", "symbol": symbol, "side": side, "amount": amount}
        self.orders.append(order)
        return order

    def place_stop_loss(self, symbol, side, amount, stop_price):
        return {"id": "sl-fake", "stop_price": stop_price}

    def place_take_profit(self, symbol, side, amount, take_price):
        return {"id": "tp-fake", "take_price": take_price}


@pytest.fixture
def gateway(tmp_path):
    limits = GatewayLimits(
        max_position_usd=1000, max_daily_loss_usd=100,
        max_orders_per_minute=3, allowed_symbols=("BTC/USDT", "ETH/USDT"),
    )
    conn = FakeConnector(price=100.0)
    return TradingGateway(conn, limits, risk_cfg=None,
                           audit_log_path=str(tmp_path / "audit.jsonl")), conn


def test_symbol_not_allowed_is_rejected(gateway):
    gw, conn = gateway
    with pytest.raises(GatewayRejection):
        gw.execute_signal("dashia", "open_long", "DOGE/USDT", equity_usd=5000)
    assert len(conn.orders) == 0


def test_valid_order_goes_through(gateway):
    gw, conn = gateway
    result = gw.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=5000)
    assert result["symbol"] == "BTC/USDT"
    assert len(conn.orders) == 1


def test_position_size_over_limit_is_rejected(gateway):
    gw, conn = gateway
    # con el fallback de sizing (2% del equity) y equity muy alto, el notional supera max_position_usd
    with pytest.raises(GatewayRejection):
        gw.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=100_000)


def test_rate_limit_blocks_after_threshold(gateway):
    gw, conn = gateway
    for _ in range(3):
        gw.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=100)
    with pytest.raises(GatewayRejection):
        gw.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=100)


def test_circuit_breaker_trips_and_blocks_new_orders(gateway):
    gw, conn = gateway
    gw.record_fill_pnl(-60)
    gw.record_fill_pnl(-50)  # total -110, supera max_daily_loss_usd=100
    with pytest.raises(CircuitBreakerTripped):
        gw.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=100)


def test_audit_log_is_written(gateway):
    gw, conn = gateway
    gw.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=100)
    assert gw.audit_path.exists()
    lines = gw.audit_path.read_text().strip().split("\n")
    assert len(lines) >= 1
    assert '"event": "order"' in lines[-1]
