"""
test_vault_bridge.py
======================
El test de punta a punta real de esta pieza: guardar credenciales en la
bóveda -> armar UnifiedMarketData -> pedir un precio -> que le llegue al
conector correcto con el símbolo correcto.
"""
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from credentials_vault.crypto import EnvelopeCipher
from credentials_vault.store import CredentialsVault
from market_data.vault_bridge import build_market_data_for_user
from market_data.router import NoVenueAvailableError

import base58
from solders.keypair import Keypair


@pytest.fixture
def vault(tmp_path):
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    v = CredentialsVault(db_path=str(tmp_path / "vault.db"), cipher=cipher)
    yield v
    v.close()


@patch("binance_connector.client.ccxt.binance")
def test_user_with_one_exchange_gets_one_provider(mock_cls, vault):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 61000.0}
    mock_cls.return_value = mock_exchange

    vault.save_credential("user_1", "binance", "K", "S")
    umd = build_market_data_for_user(vault, "user_1")

    assert umd.available_venues == ["binance"]
    quote = umd.get_price("BTC")
    assert quote.price == 61000.0
    assert quote.venue == "binance"


@patch("bybit_connector.client.ccxt.bybit")
@patch("binance_connector.client.ccxt.binance")
def test_user_with_two_exchanges_gets_fallback_between_them(mock_binance_cls, mock_bybit_cls, vault):
    mock_binance = MagicMock()
    mock_binance.fetch_ticker.side_effect = RuntimeError("símbolo no existe en binance")
    mock_binance_cls.return_value = mock_binance

    mock_bybit = MagicMock()
    mock_bybit.fetch_ticker.return_value = {"last": 61050.0}
    mock_bybit_cls.return_value = mock_bybit

    vault.save_credential("user_1", "binance", "K1", "S1")
    vault.save_credential("user_1", "bybit", "K2", "S2")
    umd = build_market_data_for_user(vault, "user_1")

    quote = umd.get_price("BTC")  # binance falla, cae a bybit
    assert quote.venue == "bybit"
    assert quote.price == 61050.0


def test_user_with_unsupported_exchange_gets_no_providers_but_does_not_crash(vault):
    vault.save_credential("user_1", "coinbase", "K", "S")
    umd = build_market_data_for_user(vault, "user_1")
    assert umd.available_venues == []
    with pytest.raises(NoVenueAvailableError):
        umd.get_price("BTC")


def test_user_with_no_connections_gets_empty_market_data(vault):
    umd = build_market_data_for_user(vault, "user_sin_nada")
    assert umd.available_venues == []


@patch("binance_connector.client.ccxt.binance")
def test_two_users_get_independent_market_data(mock_cls, vault):
    mock_exchange_1 = MagicMock()
    mock_exchange_1.fetch_ticker.return_value = {"last": 100.0}
    mock_cls.return_value = mock_exchange_1

    vault.save_credential("user_1", "binance", "K1", "S1")
    # user_2 no tiene nada conectado
    umd_1 = build_market_data_for_user(vault, "user_1")
    umd_2 = build_market_data_for_user(vault, "user_2")

    assert umd_1.available_venues == ["binance"]
    assert umd_2.available_venues == []


def test_solana_credential_builds_working_provider(vault):
    kp = Keypair()
    secret_b58 = base58.b58encode(bytes(kp)).decode()

    vault.save_credential("user_1", "solana", str(kp.pubkey()), secret_b58)
    umd = build_market_data_for_user(vault, "user_1")
    assert "solana" in umd.available_venues


def test_solana_credential_with_invalid_secret_is_skipped_gracefully(vault):
    vault.save_credential("user_1", "solana", "algun_pubkey", "esto-no-es-una-llave-base58-valida")
    umd = build_market_data_for_user(vault, "user_1")
    assert "solana" not in umd.available_venues
