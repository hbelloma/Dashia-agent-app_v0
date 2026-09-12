"""
test_jupiter_client.py
=======================
requests.get/post mockeados — valida el parseo de la API sin tocar red.
"""
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from solana_connector.config import SolanaSettings
from solana_connector.jupiter_client import JupiterClient, JupiterAPIError


def _settings():
    return SolanaSettings(rpc_url="https://x", jupiter_base_url="https://lite-api.jup.ag/swap/v1")


@patch("solana_connector.jupiter_client.requests.get")
def test_get_quote_parses_response(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"inAmount": "1000000", "outAmount": "162000", "priceImpactPct": "0.02"}
    mock_get.return_value = mock_resp

    client = JupiterClient(_settings())
    quote = client.get_quote("MINT_A", "MINT_B", 1_000_000)
    assert quote["outAmount"] == "162000"
    called_url = mock_get.call_args[0][0]
    assert called_url.endswith("/quote")


@patch("solana_connector.jupiter_client.requests.post")
def test_get_swap_transaction_returns_b64(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"swapTransaction": "abc123=="}
    mock_post.return_value = mock_resp

    client = JupiterClient(_settings())
    tx = client.get_swap_transaction({"inAmount": "1"}, "SomePubkey111")
    assert tx == "abc123=="


@patch("solana_connector.jupiter_client.requests.post")
def test_get_swap_transaction_raises_on_missing_field(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"error": "no route found"}
    mock_post.return_value = mock_resp

    client = JupiterClient(_settings())
    try:
        client.get_swap_transaction({"inAmount": "1"}, "SomePubkey111")
        assert False, "debió lanzar JupiterAPIError"
    except JupiterAPIError:
        pass


def test_resolve_mint_by_symbol_uses_well_known_table_without_network():
    client = JupiterClient(_settings())
    assert client.resolve_mint_by_symbol("SOL") == "So11111111111111111111111111111111111111112"
    assert client.resolve_mint_by_symbol("usdc") == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _settings_v2():
    return SolanaSettings(rpc_url="https://x", jupiter_v2_base_url="https://api.jup.ag/swap/v2",
                           jupiter_api_key="fake-key-123")


def test_resolve_mint_by_symbol_without_api_key_raises_for_unknown():
    client = JupiterClient(_settings())
    try:
        client.resolve_mint_by_symbol("SOMEWEIRDTOKEN")
        assert False, "debió lanzar JupiterAPIError sin JUPITER_API_KEY"
    except JupiterAPIError:
        pass


# ---------------------------------------------------------------------------
# v2 — /order y /execute
# ---------------------------------------------------------------------------
def test_get_order_without_api_key_raises_clear_error():
    client = JupiterClient(_settings())  # sin API key
    try:
        client.get_order("MINT_A", "MINT_B", 1_000_000, "SomePubkey111")
        assert False, "get_order() sin JUPITER_API_KEY debió fallar"
    except JupiterAPIError as e:
        assert "JUPITER_API_KEY" in str(e)


@patch("solana_connector.jupiter_client.requests.get")
def test_get_order_sends_api_key_header_and_taker(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "inAmount": "1000000", "outAmount": "162000", "priceImpactPct": "0.02",
        "transaction": "ZmFrZV90eA==", "requestId": "req-abc-123",
    }
    mock_get.return_value = mock_resp

    client = JupiterClient(_settings_v2())
    order = client.get_order("MINT_A", "MINT_B", 1_000_000, "TakerPubkey111")

    assert order["requestId"] == "req-abc-123"
    assert order["transaction"] == "ZmFrZV90eA=="
    args, kwargs = mock_get.call_args
    assert args[0].endswith("/order")
    assert kwargs["headers"]["x-api-key"] == "fake-key-123"
    assert kwargs["params"]["taker"] == "TakerPubkey111"


@patch("solana_connector.jupiter_client.requests.get")
def test_get_order_raises_when_transaction_missing(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"transaction": None, "errorCode": "COULD_NOT_FIND_ANY_ROUTE"}
    mock_get.return_value = mock_resp

    client = JupiterClient(_settings_v2())
    try:
        client.get_order("MINT_A", "MINT_B", 1_000_000, "TakerPubkey111")
        assert False
    except JupiterAPIError as e:
        assert "COULD_NOT_FIND_ANY_ROUTE" in str(e)


def test_execute_order_without_api_key_raises_clear_error():
    client = JupiterClient(_settings())
    try:
        client.execute_order("ZmFrZQ==", "req-123")
        assert False
    except JupiterAPIError as e:
        assert "JUPITER_API_KEY" in str(e)


@patch("solana_connector.jupiter_client.requests.post")
def test_execute_order_sends_signed_tx_and_request_id(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"signature": "real-signature-xyz", "status": "Success"}
    mock_post.return_value = mock_resp

    client = JupiterClient(_settings_v2())
    result = client.execute_order("ZmFrZV9zaWduZWRfdHg=", "req-abc-123")

    assert result["signature"] == "real-signature-xyz"
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/execute")
    assert kwargs["json"]["signedTransaction"] == "ZmFrZV9zaWduZWRfdHg="
    assert kwargs["json"]["requestId"] == "req-abc-123"


@patch("solana_connector.jupiter_client.requests.post")
def test_execute_order_raises_when_status_failed(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "Failed", "error": "slippage tolerance exceeded"}
    mock_post.return_value = mock_resp

    client = JupiterClient(_settings_v2())
    try:
        client.execute_order("ZmFrZQ==", "req-123")
        assert False
    except JupiterAPIError:
        pass
