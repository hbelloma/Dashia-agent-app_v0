"""
test_connector_factory.py
===========================
El flujo completo: guardar credencial en la bóveda -> obtener un
conector real -> verificar permisos -> quedar marcado en la bóveda.
Prueba los 3 exchanges, incluidas sus diferencias reales (Weex sin
verificación automática).
"""
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from credentials_vault.crypto import EnvelopeCipher
from credentials_vault.store import CredentialsVault
from credentials_vault.connector_factory import get_connector, connect_and_verify

from binance_connector.client import BinanceConnector, TradeOnlyViolation as BinanceTOV
from bybit_connector.client import BybitConnector
from weex_connector.client import WeexConnector, PermissionCheckUnavailable


@pytest.fixture
def vault(tmp_path):
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    v = CredentialsVault(db_path=str(tmp_path / "vault.db"), cipher=cipher)
    yield v
    v.close()


@patch("binance_connector.client.ccxt.binance")
def test_get_connector_returns_binance_instance_with_right_credentials(mock_cls, vault):
    mock_cls.return_value = MagicMock()
    vault.save_credential("user_1", "binance", "MY_KEY", "MY_SECRET", testnet=True)

    conn = get_connector(vault, "user_1", "binance", market_type="spot")
    assert isinstance(conn, BinanceConnector)
    args, kwargs = mock_cls.call_args
    assert args[0]["apiKey"] == "MY_KEY"
    assert args[0]["secret"] == "MY_SECRET"


@patch("bybit_connector.client.ccxt.bybit")
def test_get_connector_returns_bybit_instance(mock_cls, vault):
    mock_cls.return_value = MagicMock()
    vault.save_credential("user_1", "bybit", "BYBIT_KEY", "BYBIT_SECRET")
    conn = get_connector(vault, "user_1", "bybit")
    assert isinstance(conn, BybitConnector)


@patch("weex_connector.client.ccxt.weex")
def test_get_connector_returns_weex_instance(mock_cls, vault):
    mock_cls.return_value = MagicMock()
    vault.save_credential("user_1", "weex", "WEEX_KEY", "WEEX_SECRET")
    conn = get_connector(vault, "user_1", "weex")
    assert isinstance(conn, WeexConnector)


def test_unsupported_exchange_raises_clear_error(vault):
    vault.save_credential("user_1", "coinbase", "K", "S")
    with pytest.raises(ValueError):
        get_connector(vault, "user_1", "coinbase")


@patch("binance_connector.client.ccxt.binance")
def test_connect_and_verify_marks_vault_when_binance_permissions_ok(mock_cls, vault):
    mock_exchange = MagicMock()
    mock_exchange.sapiGetAccountApiRestrictions.return_value = {"enableWithdrawals": False}
    mock_cls.return_value = mock_exchange

    vault.save_credential("user_1", "binance", "K", "S")
    assert vault.get_credential("user_1", "binance").permissions_verified is False

    connect_and_verify(vault, "user_1", "binance")
    assert vault.get_credential("user_1", "binance").permissions_verified is True


@patch("binance_connector.client.ccxt.binance")
def test_connect_and_verify_does_not_mark_vault_when_withdrawal_enabled(mock_cls, vault):
    mock_exchange = MagicMock()
    mock_exchange.sapiGetAccountApiRestrictions.return_value = {"enableWithdrawals": True}
    mock_cls.return_value = mock_exchange

    vault.save_credential("user_1", "binance", "K", "S")
    with pytest.raises(BinanceTOV):
        connect_and_verify(vault, "user_1", "binance")
    # la credencial NUNCA queda marcada como verificada si falla la comprobación
    assert vault.get_credential("user_1", "binance").permissions_verified is False


@patch("weex_connector.client.ccxt.weex")
def test_connect_and_verify_weex_requires_explicit_manual_confirmation(mock_cls, vault):
    mock_cls.return_value = MagicMock()
    vault.save_credential("user_1", "weex", "K", "S")

    with pytest.raises(PermissionCheckUnavailable):
        connect_and_verify(vault, "user_1", "weex", manual_trade_only_confirmed=False)
    assert vault.get_credential("user_1", "weex").permissions_verified is False

    connect_and_verify(vault, "user_1", "weex", manual_trade_only_confirmed=True)
    assert vault.get_credential("user_1", "weex").permissions_verified is True


@patch("bybit_connector.client.ccxt.bybit")
@patch("binance_connector.client.ccxt.binance")
def test_two_users_can_have_independent_credentials_for_same_exchange(mock_binance_cls, mock_bybit_cls, vault):
    mock_binance_cls.return_value = MagicMock(
        sapiGetAccountApiRestrictions=MagicMock(return_value={"enableWithdrawals": False})
    )
    vault.save_credential("user_1", "binance", "KEY_USER_1", "SECRET_USER_1")
    vault.save_credential("user_2", "binance", "KEY_USER_2", "SECRET_USER_2")

    get_connector(vault, "user_1", "binance")
    args1, _ = mock_binance_cls.call_args
    get_connector(vault, "user_2", "binance")
    args2, _ = mock_binance_cls.call_args

    assert args1[0]["apiKey"] == "KEY_USER_1"
    assert args2[0]["apiKey"] == "KEY_USER_2"
