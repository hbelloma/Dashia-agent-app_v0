"""
wallet.py
=========
Maneja la wallet OPERATIVA (hot wallet de fondos acotados) que el backend
usa para firmar y enviar swaps automáticos. La Phantom principal del
usuario jamás entrega su llave privada — solo la usa para depositar/
retirar hacia/desde esta wallet operativa (eso se firma en el cliente,
vía wallet-adapter, no aquí). Ver README, sección de arquitectura.
"""

from __future__ import annotations
import base64
import base58
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders import message
from solders.transaction import VersionedTransaction

from .config import TradingWalletCredentials


class TradingWallet:
    def __init__(self, creds: TradingWalletCredentials):
        self._keypair = Keypair.from_bytes(base58.b58decode(creds.secret_key_b58))

    @property
    def pubkey(self) -> Pubkey:
        return self._keypair.pubkey()

    @property
    def pubkey_str(self) -> str:
        return str(self._keypair.pubkey())

    def sign_versioned_tx_b64(self, swap_transaction_b64: str) -> bytes:
        """
        Recibe el `swapTransaction` (base64) que devuelve la API de
        Jupiter, lo firma con la wallet operativa y devuelve los bytes
        listos para enviar por RPC (sendTransaction).
        """
        raw_tx = VersionedTransaction.from_bytes(base64.b64decode(swap_transaction_b64))
        signature = self._keypair.sign_message(message.to_bytes_versioned(raw_tx.message))
        signed_tx = VersionedTransaction.populate(raw_tx.message, [signature])
        return bytes(signed_tx)

    @staticmethod
    def generate_new() -> tuple[str, str]:
        """
        Genera una wallet operativa nueva. Devuelve (pubkey, secret_b58).
        El flujo real: se genera una vez por usuario/agente, se guarda el
        secret cifrado en la bóveda del backend (nunca en el dispositivo),
        y se le pide al usuario depositar un monto acotado desde su
        Phantom principal hacia el pubkey generado.
        """
        kp = Keypair()
        return str(kp.pubkey()), base58.b58encode(bytes(kp)).decode()


if __name__ == "__main__":
    pubkey, secret = TradingWallet.generate_new()
    print(f"Nueva wallet operativa generada.\nPubkey (compartible): {pubkey}")
    print("Secret (guardar SOLO en el vault del backend, nunca en git/logs):")
    print(secret)
