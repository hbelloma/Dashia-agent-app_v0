"""test_geckoterminal_client.py"""
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from market_data.geckoterminal_client import GeckoTerminalClient, GeckoTerminalAPIError


@patch("market_data.geckoterminal_client.requests.get")
def test_get_ohlcv_by_token_parses_ohlcv_list(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {"attributes": {"ohlcv_list": [
            [1700000000, 148.0, 149.0, 147.5, 148.8, 123456.0],
            [1699996400, 147.0, 148.5, 146.9, 148.0, 98765.0],
        ]}}
    }
    mock_get.return_value = mock_resp

    client = GeckoTerminalClient(network="solana")
    rows = client.get_ohlcv_by_token("So1111...token", timeframe="hour", aggregate=1, limit=2)
    assert len(rows) == 2
    assert rows[0][4] == 148.8  # close de la primera vela

    args, kwargs = mock_get.call_args
    assert "/networks/solana/tokens/So1111...token/ohlcv/hour" in args[0]


@patch("market_data.geckoterminal_client.requests.get")
def test_raises_clear_error_on_non_200(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "rate limited"
    mock_get.return_value = mock_resp

    client = GeckoTerminalClient()
    try:
        client.get_ohlcv_by_token("cualquier_direccion")
        assert False
    except GeckoTerminalAPIError:
        pass


@patch("market_data.geckoterminal_client.requests.get")
def test_raises_clear_error_on_unexpected_shape(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"algo": "inesperado"}
    mock_get.return_value = mock_resp

    client = GeckoTerminalClient()
    try:
        client.get_ohlcv_by_token("direccion")
        assert False
    except GeckoTerminalAPIError:
        pass


@patch("market_data.geckoterminal_client.requests.get")
def test_no_api_key_needed_in_headers(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"attributes": {"ohlcv_list": []}}}
    mock_get.return_value = mock_resp

    GeckoTerminalClient().get_ohlcv_by_token("direccion")
    _, kwargs = mock_get.call_args
    assert "headers" not in kwargs or not kwargs.get("headers")
