"""test_birdeye_client.py"""
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from market_data.birdeye_client import BirdeyeClient, BirdeyeAPIError


@patch("market_data.birdeye_client.requests.get")
def test_get_ohlcv_base_quote_parses_items(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {"items": [
            {"o": 148.2, "h": 149.0, "l": 147.8, "c": 148.9, "v": 12345.0, "unixTime": 1700000000, "type": "1H"},
        ]},
        "success": True,
    }
    mock_get.return_value = mock_resp

    client = BirdeyeClient(api_key="fake-key")
    items = client.get_ohlcv_base_quote("MINT_SOL", "MINT_USDC", "1H", 1699996400, 1700000000)
    assert len(items) == 1
    assert items[0]["c"] == 148.9

    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["X-API-KEY"] == "fake-key"
    assert kwargs["headers"]["x-chain"] == "solana"


@patch("market_data.birdeye_client.requests.get")
def test_raises_on_success_false(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": False, "message": "invalid address"}
    mock_get.return_value = mock_resp

    client = BirdeyeClient(api_key="fake-key")
    try:
        client.get_ohlcv_base_quote("BAD", "BAD2", "1H", 0, 100)
        assert False
    except BirdeyeAPIError:
        pass


@patch("market_data.birdeye_client.requests.get")
def test_raises_on_non_200(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"
    mock_get.return_value = mock_resp

    client = BirdeyeClient(api_key="clave-invalida")
    try:
        client.get_ohlcv_base_quote("A", "B", "1H", 0, 100)
        assert False
    except BirdeyeAPIError:
        pass


@patch("market_data.birdeye_client.requests.get")
def test_get_latest_price_returns_most_recent_point(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"items": [
        {"unixTime": 1700000000, "value": 148.0},
        {"unixTime": 1700000060, "value": 148.5},
    ]}}
    mock_get.return_value = mock_resp

    client = BirdeyeClient(api_key="k")
    assert client.get_latest_price("MINT_SOL") == 148.5
