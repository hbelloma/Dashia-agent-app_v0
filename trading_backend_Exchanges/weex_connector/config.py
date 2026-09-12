"""config.py — mismo patrón que los otros dos conectores."""
from __future__ import annotations
import os
from dataclasses import dataclass


class MissingCredentialsError(RuntimeError):
    pass


@dataclass(frozen=True)
class WeexCredentials:
    api_key: str
    api_secret: str
    testnet: bool = True

    @classmethod
    def from_env(cls, prefix: str = "WEEX") -> "WeexCredentials":
        key = os.getenv(f"{prefix}_API_KEY")
        secret = os.getenv(f"{prefix}_API_SECRET")
        testnet = os.getenv(f"{prefix}_TESTNET", "true").lower() in ("1", "true", "yes")
        if not key or not secret:
            raise MissingCredentialsError(f"Faltan {prefix}_API_KEY / {prefix}_API_SECRET en el entorno.")
        return cls(api_key=key, api_secret=secret, testnet=testnet)
