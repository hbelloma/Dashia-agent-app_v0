"""
vault_bridge.py
================
El cierre del círculo: de "lo que este usuario tiene conectado en la
bóveda" a "un UnifiedMarketData listo para que su agente pida precios".

Degradación explícita: si un venue falla al instanciarse (credencial
mala, ccxt no puede armar el cliente, etc.), se salta ese venue y se
sigue con los demás — un usuario con Binance roto pero Solana bien
conectado debería poder seguir pidiendo el precio de SOL.
"""

from __future__ import annotations
import logging

from credentials_vault.connector_factory import get_connector
from .providers import CEXMarketDataProvider, SolanaMarketDataProvider
from .router import UnifiedMarketData

log = logging.getLogger("market_data.vault_bridge")

CEX_EXCHANGES = ("binance", "bybit", "weex")


def build_market_data_for_user(vault, user_id: str, market_type: str = "spot",
                                cache_ttl_s: float = 5.0) -> UnifiedMarketData:
    providers = {}
    for cred in vault.list_credentials(user_id):
        exchange = cred.exchange
        try:
            if exchange in CEX_EXCHANGES:
                connector = get_connector(vault, user_id, exchange, market_type=market_type, label=cred.label)
                providers[exchange] = CEXMarketDataProvider(connector, exchange)

            elif exchange == "solana":
                # Solana no usa el patrón api_key/api_secret de un exchange — se
                # guarda la llave secreta base58 de la wallet operativa en
                # api_secret (ver solana_connector/wallet.py). api_key queda
                # libre para guardar el pubkey, solo como referencia.
                import os
                from solana_connector.config import SolanaSettings, TradingWalletCredentials
                from solana_connector.jupiter_client import JupiterClient
                from solana_connector.wallet import TradingWallet
                from .birdeye_client import BirdeyeClient
                from .geckoterminal_client import GeckoTerminalClient

                wallet_creds = TradingWalletCredentials(secret_key_b58=cred.api_secret)
                TradingWallet(wallet_creds)  # valida que la llave decodifica correctamente

                birdeye_key = os.getenv("BIRDEYE_API_KEY")
                birdeye_client = BirdeyeClient(api_key=birdeye_key) if birdeye_key else None
                if not birdeye_key:
                    log.info("BIRDEYE_API_KEY no configurada — el histórico de Solana usará "
                             "solo GeckoTerminal (gratis, pero límite más bajo)")
                geckoterminal_client = GeckoTerminalClient()  # gratis, sin key

                providers["solana"] = SolanaMarketDataProvider(
                    JupiterClient(SolanaSettings.from_env()),
                    birdeye_client=birdeye_client,
                    geckoterminal_client=geckoterminal_client,
                )

            else:
                log.info("Exchange '%s' guardado en la bóveda pero sin proveedor de market_data aún", exchange)

        except Exception as e:
            log.warning("No se pudo armar el proveedor de datos para '%s' (user=%s): %s", exchange, user_id, e)
            continue

    return UnifiedMarketData(providers, cache_ttl_s=cache_ttl_s)
