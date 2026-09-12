"""
config.py
=========
Igual que en binance_connector: credenciales por variables de entorno,
nunca hardcodeadas. Ver README para la diferencia clave de este lado:
la wallet aquí es una "hot wallet operativa" con fondos acotados, NO la
Phantom principal del usuario (esa nunca suelta su llave privada — ver
sección "Arquitectura: por qué una wallet operativa" del README).
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field


class MissingCredentialsError(RuntimeError):
    pass


# Mints que sí estoy seguro de tener correctos (aparecen verificados en
# múltiples fuentes). Todo lo demás se resuelve en tiempo real vía
# resolve_mint_by_symbol() en jupiter_client.py — ver README sobre por
# qué no hardcodeo una tabla larga de direcciones adivinadas.
WELL_KNOWN_MINTS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}


@dataclass(frozen=True)
class SolanaSettings:
    rpc_url: str = "https://api.mainnet-beta.solana.com"  # reemplazar por Helius/Triton en producción
    jupiter_base_url: str = "https://lite-api.jup.ag/swap/v1"  # v1 LEGACY, sin API key, rate-limited
    jupiter_v2_base_url: str = "https://api.jup.ag/swap/v2"     # v2 ACTUAL — requiere API key siempre
    jupiter_api_key: str | None = None  # obligatoria para v2; opcional en v1 (solo mejora rate limit)
    default_slippage_bps: int = 50  # 0.50%

    @property
    def use_v2(self) -> bool:
        """
        v2 (order+execute) es la API vigente y recomendada por Jupiter —
        mejor precio (compite JupiterZ/RFQ además del ruteo on-chain) y
        landing gestionado por ellos. Pero a diferencia de v1, v2 NO
        tiene un nivel gratis sin API key (confirmado contra
        developers.jup.ag/docs/swap: "All endpoints require an API key").
        Sin JUPITER_API_KEY, se cae automáticamente a v1 (gratis, más
        simple, pero vos manejás vos mismo el envío por RPC).
        """
        return self.jupiter_api_key is not None

    @classmethod
    def from_env(cls) -> "SolanaSettings":
        api_key = os.getenv("JUPITER_API_KEY") or None
        base = "https://api.jup.ag/swap/v1" if api_key else os.getenv(
            "JUPITER_BASE_URL", "https://lite-api.jup.ag/swap/v1")
        return cls(
            rpc_url=os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"),
            jupiter_base_url=base,
            jupiter_v2_base_url=os.getenv("JUPITER_V2_BASE_URL", "https://api.jup.ag/swap/v2"),
            jupiter_api_key=api_key,
            default_slippage_bps=int(os.getenv("JUPITER_SLIPPAGE_BPS", "50")),
        )


@dataclass(frozen=True)
class TradingWalletCredentials:
    secret_key_b58: str  # llave privada de la wallet OPERATIVA (no la Phantom principal)

    @classmethod
    def from_env(cls, var: str = "SOLANA_TRADING_WALLET_SECRET") -> "TradingWalletCredentials":
        val = os.getenv(var)
        if not val:
            raise MissingCredentialsError(
                f"Falta {var} en el entorno. Generar una wallet operativa nueva con "
                f"`python -m solana_connector.wallet` y financiarla con un monto acotado "
                f"desde Phantom — nunca reusar la seed phrase principal del usuario aquí."
            )
        return cls(secret_key_b58=val)


@dataclass
class SolanaGatewayLimits:
    """Ver blueprint_arquitectura_seguridad.md §4 — misma filosofía que GatewayLimits de Binance."""
    max_position_usd: float = 200.0
    max_daily_loss_usd: float = 80.0
    max_orders_per_minute: int = 4
    allowed_symbols: tuple = ("SOL", "JUP", "BONK", "WIF")  # whitelist por símbolo, resuelto a mint en runtime
    max_slippage_bps: int = 100  # rechaza swaps con más de 1% de slippage cotizado
