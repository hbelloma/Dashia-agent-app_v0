"""
crypto.py
=========
Envelope encryption real (no un mock): cada credencial se cifra con una
DEK (Data Encryption Key) única generada al momento; esa DEK se cifra a
su vez con una KEK (Key Encryption Key) maestra. Esto es exactamente el
patrón descrito en blueprint_arquitectura_seguridad.md §2.

Diferencia honesta con producción: acá la KEK vive en una variable de
entorno (VAULT_MASTER_KEY). En producción esa KEK NUNCA debe vivir en
una variable de entorno de la app — debe vivir en un KMS/HSM gestionado
(AWS KMS, GCP KMS, HashiCorp Vault) y esta clase debería llamar a ese
servicio para cifrar/descifrar la DEK en vez de hacerlo localmente. La
interfaz (`encrypt_secret` / `decrypt_secret`) es la misma en ambos
casos — cambiar de "KEK local" a "KEK en KMS" no debería tocar el resto
del código, solo esta clase.
"""

from __future__ import annotations
import os
import base64
from dataclasses import dataclass
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class VaultDecryptionError(RuntimeError):
    """La credencial fue alterada, o se está usando la KEK equivocada."""


class MissingMasterKeyError(RuntimeError):
    pass


@dataclass
class EncryptedSecret:
    ciphertext: bytes      # el secreto, cifrado con la DEK
    encrypted_dek: bytes   # la DEK, cifrada con la KEK

    def to_storage(self) -> str:
        """Formato compacto para guardar en una sola columna de DB."""
        return base64.b64encode(self.ciphertext).decode() + "." + base64.b64encode(self.encrypted_dek).decode()

    @classmethod
    def from_storage(cls, raw: str) -> "EncryptedSecret":
        ct_b64, dek_b64 = raw.split(".", 1)
        return cls(ciphertext=base64.b64decode(ct_b64), encrypted_dek=base64.b64decode(dek_b64))


class EnvelopeCipher:
    def __init__(self, master_key: bytes | None = None):
        """
        master_key: la KEK, en formato Fernet (32 bytes url-safe base64).
        Si no se pasa, se lee de VAULT_MASTER_KEY. En producción esto se
        reemplaza por una llamada a KMS, no por leer una env var.
        """
        raw = master_key or os.getenv("VAULT_MASTER_KEY")
        if not raw:
            raise MissingMasterKeyError(
                "Falta VAULT_MASTER_KEY. Generar una con "
                "`python -m credentials_vault.crypto` y guardarla en el "
                "vault del entorno (KMS en producción, nunca en git)."
            )
        self._kek = Fernet(raw if isinstance(raw, bytes) else raw.encode())

    def encrypt_secret(self, plaintext: str) -> EncryptedSecret:
        dek = Fernet.generate_key()
        ciphertext = Fernet(dek).encrypt(plaintext.encode())
        encrypted_dek = self._kek.encrypt(dek)
        return EncryptedSecret(ciphertext=ciphertext, encrypted_dek=encrypted_dek)

    def decrypt_secret(self, secret: EncryptedSecret) -> str:
        try:
            dek = self._kek.decrypt(secret.encrypted_dek)
            plaintext = Fernet(dek).decrypt(secret.ciphertext)
            return plaintext.decode()
        except InvalidToken as e:
            raise VaultDecryptionError(
                "No se pudo descifrar — la KEK no coincide o el dato fue alterado"
            ) from e

    @staticmethod
    def generate_master_key() -> str:
        return Fernet.generate_key().decode()

    @staticmethod
    def derive_master_key_from_passphrase(passphrase: str, salt: bytes) -> str:
        """Alternativa si se prefiere derivar la KEK de una passphrase en vez
        de generarla al azar (p.ej. para entornos de desarrollo locales)."""
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480_000)
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return key.decode()


if __name__ == "__main__":
    print("Nueva VAULT_MASTER_KEY (guardar en el vault del entorno, no en git):")
    print(EnvelopeCipher.generate_master_key())
