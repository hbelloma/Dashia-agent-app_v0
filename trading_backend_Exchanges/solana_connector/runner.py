"""
runner.py
=========
Ejemplo de punta a punta para el lado Solana. A diferencia de Binance,
aquí no hay un solo endpoint de velas OHLCV "oficial" — en producción
esto se alimentaría con datos de un agregador de precios (Birdeye,
CoinGecko, o el propio historial de swaps) formateados igual que
dashia_engine espera. Este runner usa un `price_feed_fn` inyectable para
no acoplarse a una fuente de datos específica.

No se ejecutó contra la red real desde este sandbox (sin salida a
jup.ag ni a RPCs de Solana). Antes de usar dinero real: generar una
wallet operativa nueva (`python -m solana_connector.wallet`), financiarla
con un monto pequeño desde Phantom, y probar primero con montos mínimos.
"""
import logging
import time

from dashia_engine import DashiaConfig, run_dashia, RiskConfig

from .config import SolanaSettings, SolanaGatewayLimits, TradingWalletCredentials
from .jupiter_client import JupiterClient
from .wallet import TradingWallet
from .rpc import SolanaRPC
from .gateway import SolanaTradingGateway

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("solana_runner")

SYMBOL = "SOL"
AGENT_ID = "dashia"


def main(price_feed_fn):
    """
    price_feed_fn: función sin argumentos que devuelve un DataFrame OHLCV
    reciente para SOL/USDC (mismo formato que dashia_engine espera).
    """
    settings = SolanaSettings.from_env()
    wallet = TradingWallet(TradingWalletCredentials.from_env())
    jupiter = JupiterClient(settings)
    rpc = SolanaRPC(settings)

    log.info("Wallet operativa: %s", wallet.pubkey_str)
    log.info("Balance SOL: %.4f", rpc.get_balance_sol(wallet.pubkey_str))

    risk_cfg = RiskConfig(plan="WALK", risk_capital_pct=10, sltp_method="PERCENTAGE",
                           stop_loss_pct=3.0, take_profit_pct=8.0)
    gateway = SolanaTradingGateway(jupiter, wallet, rpc, SolanaGatewayLimits(), risk_cfg=risk_cfg)
    dashia_cfg = DashiaConfig(max_bars_back=300, risk=risk_cfg)

    while True:
        try:
            df = price_feed_fn()
            signals = run_dashia(df, dashia_cfg)
            last = signals.iloc[-1]

            if last["start_long"]:
                gateway.execute_signal(AGENT_ID, "open_long", SYMBOL, equity_usd=100)
            elif last["end_long"]:
                gateway.execute_signal(AGENT_ID, "close_long", SYMBOL, equity_usd=100)

        except Exception as e:
            log.exception("Error en el ciclo del runner: %s", e)

        time.sleep(60 * 15)


if __name__ == "__main__":
    raise SystemExit(
        "Este runner necesita un price_feed_fn real (Birdeye/CoinGecko/etc.) — "
        "ver docstring del módulo. No se puede correr standalone sin eso."
    )
