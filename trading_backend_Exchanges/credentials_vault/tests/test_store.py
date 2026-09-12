"""
test_store.py
==============
La prueba que más importa acá abajo no es "¿el código dice que cifra?"
sino "¿el archivo .db en disco tiene el texto plano adentro?" — se lee
el archivo SQLite como bytes crudos y se confirma que no.
"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from credentials_vault.crypto import EnvelopeCipher
from credentials_vault.store import CredentialsVault, CredentialNotFoundError


@pytest.fixture
def vault(tmp_path):
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    db_path = str(tmp_path / "vault.db")
    v = CredentialsVault(db_path=db_path, cipher=cipher)
    yield v, db_path
    v.close()


def test_save_and_get_roundtrip(vault):
    v, _ = vault
    v.save_credential("user_1", "binance", "APIKEY123", "SECRET456", testnet=True)
    cred = v.get_credential("user_1", "binance")
    assert cred.api_key == "APIKEY123"
    assert cred.api_secret == "SECRET456"
    assert cred.testnet is True
    assert cred.permissions_verified is False


def test_raw_db_file_never_contains_plaintext_secrets(vault):
    v, db_path = vault
    v.save_credential("user_1", "binance", "MUY_SECRETO_API_KEY", "MUY_SECRETO_SECRET", testnet=True)
    with open(db_path, "rb") as f:
        raw = f.read()
    assert b"MUY_SECRETO_API_KEY" not in raw
    assert b"MUY_SECRETO_SECRET" not in raw


def test_multiple_users_are_isolated(vault):
    v, _ = vault
    v.save_credential("user_1", "binance", "KEY_DE_USER_1", "SECRET_DE_USER_1")
    v.save_credential("user_2", "binance", "KEY_DE_USER_2", "SECRET_DE_USER_2")

    creds_1 = v.list_credentials("user_1")
    creds_2 = v.list_credentials("user_2")

    assert len(creds_1) == 1 and creds_1[0].api_key == "KEY_DE_USER_1"
    assert len(creds_2) == 1 and creds_2[0].api_key == "KEY_DE_USER_2"
    # user_1 nunca debe poder ver la credencial de user_2, ni por accidente
    assert all(c.user_id == "user_1" for c in creds_1)


def test_get_nonexistent_credential_raises_clear_error(vault):
    v, _ = vault
    with pytest.raises(CredentialNotFoundError):
        v.get_credential("user_1", "bybit")


def test_save_again_updates_and_resets_verification(vault):
    v, _ = vault
    v.save_credential("user_1", "binance", "KEY_VIEJA", "SECRET_VIEJO")
    v.mark_permissions_verified("user_1", "binance")
    assert v.get_credential("user_1", "binance").permissions_verified is True

    v.save_credential("user_1", "binance", "KEY_NUEVA", "SECRET_NUEVO")
    cred = v.get_credential("user_1", "binance")
    assert cred.api_key == "KEY_NUEVA"
    assert cred.permissions_verified is False  # cambiar la key obliga a re-verificar


def test_multiple_labels_per_user_per_exchange(vault):
    v, _ = vault
    v.save_credential("user_1", "binance", "KEY_CUENTA_A", "SECRET_A", label="cuenta_principal")
    v.save_credential("user_1", "binance", "KEY_CUENTA_B", "SECRET_B", label="cuenta_secundaria")

    creds = v.list_credentials("user_1")
    assert len(creds) == 2
    labels = {c.label for c in creds}
    assert labels == {"cuenta_principal", "cuenta_secundaria"}


def test_delete_credential(vault):
    v, _ = vault
    v.save_credential("user_1", "weex", "K", "S")
    v.delete_credential("user_1", "weex")
    with pytest.raises(CredentialNotFoundError):
        v.get_credential("user_1", "weex")


def test_mark_permissions_verified_sets_timestamp(vault):
    v, _ = vault
    v.save_credential("user_1", "bybit", "K", "S")
    v.mark_permissions_verified("user_1", "bybit")
    cred = v.get_credential("user_1", "bybit")
    assert cred.permissions_verified is True
    assert cred.permissions_verified_at is not None
