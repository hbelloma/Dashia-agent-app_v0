"""
test_crypto.py
===============
Cifrado real con la librería `cryptography` — nada de esto es mock.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from credentials_vault.crypto import EnvelopeCipher, EncryptedSecret, VaultDecryptionError, MissingMasterKeyError


def test_encrypt_decrypt_roundtrip():
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    secret = cipher.encrypt_secret("mi-api-key-super-secreta")
    assert cipher.decrypt_secret(secret) == "mi-api-key-super-secreta"


def test_ciphertext_does_not_contain_plaintext():
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    secret = cipher.encrypt_secret("BINANCE_API_KEY_12345")
    assert b"BINANCE_API_KEY_12345" not in secret.ciphertext
    assert b"BINANCE_API_KEY_12345" not in secret.to_storage().encode()


def test_tampered_ciphertext_fails_to_decrypt():
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    secret = cipher.encrypt_secret("valor-original")
    tampered = EncryptedSecret(ciphertext=secret.ciphertext[:-4] + b"XXXX", encrypted_dek=secret.encrypted_dek)
    with pytest.raises(VaultDecryptionError):
        cipher.decrypt_secret(tampered)


def test_wrong_kek_cannot_decrypt():
    cipher_a = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    cipher_b = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    secret = cipher_a.encrypt_secret("solo cipher_a debería poder leer esto")
    with pytest.raises(VaultDecryptionError):
        cipher_b.decrypt_secret(secret)


def test_storage_roundtrip_via_string_format():
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    secret = cipher.encrypt_secret("otra-clave")
    restored = EncryptedSecret.from_storage(secret.to_storage())
    assert cipher.decrypt_secret(restored) == "otra-clave"


def test_missing_master_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("VAULT_MASTER_KEY", raising=False)
    with pytest.raises(MissingMasterKeyError):
        EnvelopeCipher()
