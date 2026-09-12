"""
store.py
========
Almacén de credenciales por usuario, cifradas en reposo con
EnvelopeCipher (crypto.py). SQLite acá para que el paquete sea
autocontenido y testeable sin infraestructura externa — en producción
esta clase se reemplaza por una tabla en Postgres con las mismas
columnas; la interfaz pública (save/get/list/delete) no cambiaría.

Aislamiento entre usuarios: CADA consulta filtra por user_id a nivel de
SQL, nunca a nivel de aplicación después de traer todo — así una capa
de autorización que se le olvide filtrar no puede filtrar credenciales
de otro usuario por accidente (ver test_store.py, hay un test específico
para esto).
"""

from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .crypto import EnvelopeCipher, EncryptedSecret
from .models import DecryptedCredential

_SCHEMA = """
CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    exchange TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT 'default',
    encrypted_api_key TEXT NOT NULL,
    encrypted_api_secret TEXT NOT NULL,
    testnet INTEGER NOT NULL DEFAULT 1,
    permissions_verified INTEGER NOT NULL DEFAULT 0,
    permissions_verified_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, exchange, label)
);
"""


class CredentialNotFoundError(RuntimeError):
    pass


class CredentialsVault:
    def __init__(self, db_path: str = "vault.db", cipher: EnvelopeCipher | None = None):
        self.cipher = cipher or EnvelopeCipher()
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def save_credential(self, user_id: str, exchange: str, api_key: str, api_secret: str,
                         label: str = "default", testnet: bool = True) -> None:
        enc_key = self.cipher.encrypt_secret(api_key).to_storage()
        enc_secret = self.cipher.encrypt_secret(api_secret).to_storage()
        self._conn.execute(
            """INSERT INTO credentials (user_id, exchange, label, encrypted_api_key,
                   encrypted_api_secret, testnet, permissions_verified, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?)
               ON CONFLICT(user_id, exchange, label) DO UPDATE SET
                   encrypted_api_key=excluded.encrypted_api_key,
                   encrypted_api_secret=excluded.encrypted_api_secret,
                   testnet=excluded.testnet,
                   permissions_verified=0,
                   permissions_verified_at=NULL""",
            (user_id, exchange, label, enc_key, enc_secret, int(testnet),
             datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def get_credential(self, user_id: str, exchange: str, label: str = "default") -> DecryptedCredential:
        row = self._conn.execute(
            """SELECT user_id, exchange, label, encrypted_api_key, encrypted_api_secret,
                      testnet, permissions_verified, permissions_verified_at, created_at
               FROM credentials WHERE user_id=? AND exchange=? AND label=?""",
            (user_id, exchange, label),
        ).fetchone()
        if row is None:
            raise CredentialNotFoundError(f"No hay credencial para user={user_id} exchange={exchange} label={label}")
        return self._row_to_credential(row)

    def list_credentials(self, user_id: str) -> list[DecryptedCredential]:
        """OJO: filtra por user_id en el SQL, no trae todo y filtra después."""
        rows = self._conn.execute(
            """SELECT user_id, exchange, label, encrypted_api_key, encrypted_api_secret,
                      testnet, permissions_verified, permissions_verified_at, created_at
               FROM credentials WHERE user_id=?""",
            (user_id,),
        ).fetchall()
        return [self._row_to_credential(r) for r in rows]

    def delete_credential(self, user_id: str, exchange: str, label: str = "default") -> None:
        self._conn.execute(
            "DELETE FROM credentials WHERE user_id=? AND exchange=? AND label=?",
            (user_id, exchange, label),
        )
        self._conn.commit()

    def mark_permissions_verified(self, user_id: str, exchange: str, label: str = "default") -> None:
        self._conn.execute(
            """UPDATE credentials SET permissions_verified=1, permissions_verified_at=?
               WHERE user_id=? AND exchange=? AND label=?""",
            (datetime.now(timezone.utc).isoformat(), user_id, exchange, label),
        )
        self._conn.commit()

    def _row_to_credential(self, row) -> DecryptedCredential:
        (user_id, exchange, label, enc_key, enc_secret, testnet,
         verified, verified_at, created_at) = row
        return DecryptedCredential(
            user_id=user_id, exchange=exchange, label=label,
            api_key=self.cipher.decrypt_secret(EncryptedSecret.from_storage(enc_key)),
            api_secret=self.cipher.decrypt_secret(EncryptedSecret.from_storage(enc_secret)),
            testnet=bool(testnet), permissions_verified=bool(verified),
            permissions_verified_at=datetime.fromisoformat(verified_at) if verified_at else None,
            created_at=datetime.fromisoformat(created_at),
        )

    def close(self):
        self._conn.close()
