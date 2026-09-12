"""
test_gateway_bridge.py
========================
Lo crítico a probar acá: código rechazado por el sandbox NUNCA debe
llegar a tocar el gateway — ni siquiera para que él lo rechace.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_sandbox.gateway_bridge import evaluate_and_execute
from agent_sandbox.process_isolation import IsolationLimits


class FakeGateway:
    def __init__(self):
        self.calls = []

    def execute_signal(self, agent_id, action, symbol, equity_usd):
        self.calls.append((agent_id, action, symbol, equity_usd))
        return {"signature": "fake-ok"}


FAST_LIMITS = IsolationLimits(cpu_seconds=2, memory_mb=64, wall_clock_timeout_s=8,
                               use_network_namespace=False)


def test_malicious_code_never_reaches_the_gateway():
    gw = FakeGateway()
    outcome = evaluate_and_execute(
        "dashia", "import os\nbuy(size=1)", "BTC/USDT",
        indicators={}, variables={"position": "none"}, equity_usd=1000,
        gateway=gw, limits=FAST_LIMITS,
    )
    assert outcome.executed is False
    assert "security" in outcome.reason
    assert gw.calls == []


def test_hold_decision_never_reaches_the_gateway():
    gw = FakeGateway()
    outcome = evaluate_and_execute(
        "dashia", 'if rsi(14) > 90:\n    buy(size=risk.default)', "BTC/USDT",
        indicators={("rsi", 14): 50}, variables={"position": "none"}, equity_usd=1000,
        gateway=gw, limits=FAST_LIMITS,
    )
    assert outcome.executed is False
    assert gw.calls == []


def test_valid_buy_from_flat_position_opens_long():
    gw = FakeGateway()
    outcome = evaluate_and_execute(
        "dashia", 'if rsi(14) < 30:\n    buy(size=risk.default)', "BTC/USDT",
        indicators={("rsi", 14): 20}, variables={"position": "none"}, equity_usd=1000,
        gateway=gw, limits=FAST_LIMITS,
    )
    assert outcome.executed is True
    assert gw.calls == [("dashia", "open_long", "BTC/USDT", 1000)]


def test_buy_while_already_long_does_nothing():
    gw = FakeGateway()
    outcome = evaluate_and_execute(
        "dashia", 'if rsi(14) < 30:\n    buy(size=risk.default)', "BTC/USDT",
        indicators={("rsi", 14): 20}, variables={"position": "long"}, equity_usd=1000,
        gateway=gw, limits=FAST_LIMITS,
    )
    assert outcome.executed is False
    assert gw.calls == []


def test_sell_while_long_closes_position():
    gw = FakeGateway()
    outcome = evaluate_and_execute(
        "dashia", 'if rsi(14) > 70:\n    sell(size=risk.default)', "BTC/USDT",
        indicators={("rsi", 14): 80}, variables={"position": "long"}, equity_usd=1000,
        gateway=gw, limits=FAST_LIMITS,
    )
    assert outcome.executed is True
    assert gw.calls == [("dashia", "close_long", "BTC/USDT", 1000)]


def test_gateway_rejection_is_reported_not_raised():
    class RejectingGateway:
        def execute_signal(self, *a, **kw):
            raise RuntimeError("símbolo no permitido")

    outcome = evaluate_and_execute(
        "dashia", 'if rsi(14) < 30:\n    buy(size=risk.default)', "DOGE/USDT",
        indicators={("rsi", 14): 20}, variables={"position": "none"}, equity_usd=1000,
        gateway=RejectingGateway(), limits=FAST_LIMITS,
    )
    assert outcome.executed is False
    assert "gateway rechazó" in outcome.reason
