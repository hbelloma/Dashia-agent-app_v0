"""
config.py
=========
Carga de configuración desde variables de entorno. Las credenciales
NUNCA se hardcodean ni se guardan en el repo — en producción, este mismo
patrón se usa para leer desde el vault/KMS del backend (ver blueprint de
seguridad, sección 2) en vez de variables de entorno planas.
"""

from __future__ import annotations
import os
from dataclasses import dataclass


class MissingCredentialsError(RuntimeError):
    pass


@dataclass(frozen=True)
class BinanceCredentials:
    api_key: str
    api_secret: str
    testnet: bool = True  # por defecto en testnet — hay que optar explícitamente por producción

    @classmethod
    def from_env(cls, prefix: str = "BINANCE") -> "BinanceCredentials":
        key = os.getenv(f"{prefix}_API_KEY")
        secret = os.getenv(f"{prefix}_API_SECRET")
        testnet = os.getenv(f"{prefix}_TESTNET", "true").lower() in ("1", "true", "yes")
        if not key or not secret:
            raise MissingCredentialsError(
                f"Faltan {prefix}_API_KEY / {prefix}_API_SECRET en el entorno. "
                f"Copia .env.example a .env y complétalo (nunca subas .env a git)."
            )
        return cls(api_key=key, api_secret=secret, testnet=testnet)


@dataclass
class GatewayLimits:
    """
    Límites duros del gateway — independientes de lo que decida el agente.
    Ver blueprint_arquitectura_seguridad.md §4.
    """
    max_position_usd: float = 500.0
    max_daily_loss_usd: float = 200.0
    max_orders_per_minute: int = 6
    allowed_symbols: tuple = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "LTC/USDT",
                               "XRP/USDT", "ARB/USDT", "XAU/USDT")
