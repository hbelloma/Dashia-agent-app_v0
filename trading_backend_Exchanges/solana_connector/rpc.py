"""
rpc.py
======
JSON-RPC directo contra el nodo de Solana (Helius, Triton, QuickNode o el
público). Se implementa a mano con `requests` en vez de solana-py: al
revisar el paquete instalado (solana==0.40.3) el cliente síncrono
`solana.rpc.api.Client` no está disponible en esa versión (solo quedó el
async), así que depender de él es frágil entre versiones. JSON-RPC crudo
es exactamente lo mismo que usa cualquier SDK por debajo, y es lo que
recomienda Helius para sus endpoints rápidos (ver README).
"""

from __future__ import annotations
import base64
import time
import logging
import requests

from .config import SolanaSettings

log = logging.getLogger("solana_rpc")


class SolanaRPCError(RuntimeError):
    pass


class SolanaRPC:
    def __init__(self, settings: SolanaSettings, timeout: float = 15.0):
        self.url = settings.rpc_url
        self.timeout = timeout

    def _call(self, method: str, params: list) -> dict:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        resp = requests.post(self.url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise SolanaRPCError(f"{method} -> {data['error']}")
        return data["result"]

    def get_balance_lamports(self, pubkey: str) -> int:
        return self._call("getBalance", [pubkey])["value"]

    def get_balance_sol(self, pubkey: str) -> float:
        return self.get_balance_lamports(pubkey) / 1_000_000_000

    def send_raw_transaction(self, signed_tx_bytes: bytes, skip_preflight: bool = False) -> str:
        b64 = base64.b64encode(signed_tx_bytes).decode()
        params = [b64, {"encoding": "base64", "skipPreflight": skip_preflight, "maxRetries": 3}]
        return self._call("sendTransaction", params)

    def get_signature_status(self, signature: str) -> dict | None:
        result = self._call("getSignatureStatuses", [[signature], {"searchTransactionHistory": True}])
        values = result.get("value", [])
        return values[0] if values else None

    def confirm_transaction(self, signature: str, timeout_s: float = 30.0, poll_interval: float = 2.0) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            status = self.get_signature_status(signature)
            if status and status.get("confirmationStatus") in ("confirmed", "finalized"):
                if status.get("err"):
                    raise SolanaRPCError(f"Transacción {signature} falló on-chain: {status['err']}")
                return True
            time.sleep(poll_interval)
        log.warning("Timeout esperando confirmación de %s", signature)
        return False
