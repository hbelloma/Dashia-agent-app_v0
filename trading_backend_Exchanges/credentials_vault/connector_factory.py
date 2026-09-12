"""
connector_factory.py
======================
El momento exacto en que una credencial cifrada en reposo se convierte
en un conector listo para operar. Esto es lo que el backend llamaría
cada vez que un agente necesita ejecutar una orden para un usuario
específico — las credenciales en texto plano solo existen en memoria,
durante esta función, nunca se loguean ni se guardan así.
"""

from __future__ import annotations
from .store import CredentialsVault

SUPPORTED_EXCHANGES = ("binance", "bybit", "weex")


def get_connector(vault: CredentialsVault, user_id: str, exchange: str,
                   market_type: str = "spot", label: str = "default"):
    exchange = exchange.lower()
    cred = vault.get_credential(user_id, exchange, label)

    if exchange == "binance":
        from binance_connector.config import BinanceCredentials
        from binance_connector.client import BinanceConnector
        creds = BinanceCredentials(api_key=cred.api_key, api_secret=cred.api_secret, testnet=cred.testnet)
        return BinanceConnector(creds, market_type=market_type)

    if exchange == "bybit":
        from bybit_connector.config import BybitCredentials
        from bybit_connector.client import BybitConnector
        creds = BybitCredentials(api_key=cred.api_key, api_secret=cred.api_secret, testnet=cred.testnet)
        return BybitConnector(creds, market_type=market_type)

    if exchange == "weex":
        from weex_connector.config import WeexCredentials
        from weex_connector.client import WeexConnector
        creds = WeexCredentials(api_key=cred.api_key, api_secret=cred.api_secret, testnet=cred.testnet)
        return WeexConnector(creds, market_type=market_type)

    raise ValueError(f"Exchange no soportado: {exchange}. Disponibles: {SUPPORTED_EXCHANGES}")


def connect_and_verify(vault: CredentialsVault, user_id: str, exchange: str,
                        market_type: str = "spot", label: str = "default",
                        manual_trade_only_confirmed: bool = False):
    """
    Flujo pensado para el momento en que el usuario conecta un exchange
    desde la app (pantalla "Conectar exchange" del prototipo). Para
    Binance/Bybit, verifica automáticamente los permisos contra el
    exchange. Para Weex, exige la confirmación manual explícita (ver
    weex_connector/README.md) — no hay atajo automático posible.
    """
    exchange = exchange.lower()
    connector = get_connector(vault, user_id, exchange, market_type, label)

    if exchange == "weex":
        connector.acknowledge_manual_trade_only_check(manual_trade_only_confirmed)
        if manual_trade_only_confirmed:
            vault.mark_permissions_verified(user_id, exchange, label)
        return connector

    connector.verify_trade_only()  # lanza si detecta permiso de retiro — la key queda sin marcar
    vault.mark_permissions_verified(user_id, exchange, label)
    return connector
