"""
test_gateway.py
================
Igual que en binance_connector: nada de red real, pero la lógica de
límites (la parte crítica de seguridad) sí se valida de punta a punta.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from solana_connector.config import SolanaGatewayLimits
from solana_connector.gateway import SolanaTradingGateway, GatewayRejection, CircuitBreakerTripped


class FakeSettings:
    def __init__(self, use_v2=False):
        self.use_v2 = use_v2


class FakeJupiter:
    def __init__(self, price_impact_pct="0.001", use_v2=False):  # 0.001 = 0.1% (Jupiter usa fracción decimal, no %)
        self.price_impact_pct = price_impact_pct
        self.calls = []
        self.settings = FakeSettings(use_v2=use_v2)

    def get_quote(self, input_mint, output_mint, amount, slippage_bps):
        self.calls.append(("quote_v1", input_mint, output_mint, amount))
        return {"inputMint": input_mint, "outputMint": output_mint,
                "outAmount": str(int(amount) * 10), "priceImpactPct": self.price_impact_pct}

    def get_swap_transaction(self, quote, user_pubkey, priority_fee_lamports="auto"):
        return "ZmFrZV9zd2FwX3R4"  # base64 dummy

    def get_order(self, input_mint, output_mint, amount, taker_pubkey, slippage_bps):
        self.calls.append(("order_v2", input_mint, output_mint, amount))
        return {"inputMint": input_mint, "outputMint": output_mint,
                "outAmount": str(int(amount) * 10), "priceImpactPct": self.price_impact_pct,
                "transaction": "ZmFrZV9vcmRlcl90eA==", "requestId": "fake-request-id-123"}

    def execute_order(self, signed_transaction_b64, request_id):
        self.calls.append(("execute_v2", request_id))
        return {"signature": f"fake-v2-sig-for-{request_id}", "status": "Success"}

    def resolve_mint_by_symbol(self, symbol):
        return f"FAKEMINT_{symbol}"


class FakeWallet:
    pubkey_str = "FakeWalletPubkey111111111111111111111111"

    def sign_versioned_tx_b64(self, b64):
        return b"signed-bytes"


class FakeRPC:
    def __init__(self):
        self.sent = []

    def send_raw_transaction(self, signed_bytes, skip_preflight=False):
        sig = f"fakesig{len(self.sent)}"
        self.sent.append(sig)
        return sig

    def confirm_transaction(self, signature, timeout_s=30):
        return True


@pytest.fixture
def gateway(tmp_path):
    limits = SolanaGatewayLimits(
        max_position_usd=100, max_daily_loss_usd=50, max_orders_per_minute=3,
        allowed_symbols=("SOL", "JUP"), max_slippage_bps=100,
    )
    jupiter, wallet, rpc = FakeJupiter(), FakeWallet(), FakeRPC()
    gw = SolanaTradingGateway(jupiter, wallet, rpc, limits, risk_cfg=None,
                               audit_log_path=str(tmp_path / "audit.jsonl"))
    return gw, jupiter, rpc


def test_symbol_not_allowed_is_rejected(gateway):
    gw, jupiter, rpc = gateway
    with pytest.raises(GatewayRejection):
        gw.execute_signal("dashia", "open_long", "BONK", equity_usd=1000)
    assert len(rpc.sent) == 0


def test_valid_open_long_goes_through(gateway):
    gw, jupiter, rpc = gateway
    result = gw.execute_signal("dashia", "open_long", "SOL", equity_usd=1000)
    assert "signature" in result
    assert len(rpc.sent) == 1


def test_close_without_open_position_is_rejected(gateway):
    gw, jupiter, rpc = gateway
    with pytest.raises(GatewayRejection):
        gw.execute_signal("dashia", "close_long", "SOL", equity_usd=1000)


def test_open_then_close_works(gateway):
    gw, jupiter, rpc = gateway
    gw.execute_signal("dashia", "open_long", "SOL", equity_usd=1000)
    result = gw.execute_signal("dashia", "close_long", "SOL", equity_usd=1000)
    assert "signature" in result
    assert len(rpc.sent) == 2


def test_high_slippage_quote_is_rejected(gateway):
    gw, jupiter, rpc = gateway
    jupiter.price_impact_pct = "0.05"  # 5% >> max_slippage_bps=100 (1%)
    with pytest.raises(GatewayRejection):
        gw.execute_signal("dashia", "open_long", "SOL", equity_usd=1000)


def test_rate_limit_blocks_after_threshold(gateway):
    gw, jupiter, rpc = gateway
    for _ in range(3):
        gw.execute_signal("dashia", "open_long", "SOL", equity_usd=100)
    with pytest.raises(GatewayRejection):
        gw.execute_signal("dashia", "open_long", "SOL", equity_usd=100)


def test_circuit_breaker_trips_and_blocks_new_orders(gateway):
    gw, jupiter, rpc = gateway
    gw.record_fill_pnl(-30)
    gw.record_fill_pnl(-25)  # total -55, supera max_daily_loss_usd=50
    with pytest.raises(CircuitBreakerTripped):
        gw.execute_signal("dashia", "open_long", "SOL", equity_usd=100)


def test_unsupported_action_is_rejected(gateway):
    gw, jupiter, rpc = gateway
    with pytest.raises(GatewayRejection):
        gw.execute_signal("dashia", "open_short", "SOL", equity_usd=100)


# ---------------------------------------------------------------------------
# v1 vs v2 — confirma que el gateway elige el camino correcto y que v2
# NO pasa por nuestro propio RPC (Jupiter gestiona el landing)
# ---------------------------------------------------------------------------
def test_v1_path_uses_get_quote_and_own_rpc(tmp_path):
    limits = SolanaGatewayLimits(allowed_symbols=("SOL",))
    jupiter, wallet, rpc = FakeJupiter(use_v2=False), FakeWallet(), FakeRPC()
    gw = SolanaTradingGateway(jupiter, wallet, rpc, limits, audit_log_path=str(tmp_path / "a.jsonl"))

    gw.execute_signal("dashia", "open_long", "SOL", equity_usd=1000)
    assert jupiter.calls[0][0] == "quote_v1"
    assert len(rpc.sent) == 1  # v1 SÍ manda la tx por nuestro propio RPC


def test_v2_path_uses_get_order_and_execute_not_own_rpc(tmp_path):
    limits = SolanaGatewayLimits(allowed_symbols=("SOL",))
    jupiter, wallet, rpc = FakeJupiter(use_v2=True), FakeWallet(), FakeRPC()
    gw = SolanaTradingGateway(jupiter, wallet, rpc, limits, audit_log_path=str(tmp_path / "a.jsonl"))

    result = gw.execute_signal("dashia", "open_long", "SOL", equity_usd=1000)
    assert jupiter.calls[0][0] == "order_v2"
    assert jupiter.calls[1][0] == "execute_v2"
    assert len(rpc.sent) == 0  # v2 NO debe tocar nuestro propio RPC — Jupiter landea
    assert "fake-v2-sig" in result["signature"]


def test_v2_execute_receives_the_request_id_from_order(tmp_path):
    limits = SolanaGatewayLimits(allowed_symbols=("SOL",))
    jupiter, wallet, rpc = FakeJupiter(use_v2=True), FakeWallet(), FakeRPC()
    gw = SolanaTradingGateway(jupiter, wallet, rpc, limits, audit_log_path=str(tmp_path / "a.jsonl"))

    gw.execute_signal("dashia", "open_long", "SOL", equity_usd=1000)
    execute_call = [c for c in jupiter.calls if c[0] == "execute_v2"][0]
    assert execute_call[1] == "fake-request-id-123"
