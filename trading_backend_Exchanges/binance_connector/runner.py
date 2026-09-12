"""
runner.py
=========
Ejemplo de punta a punta: Binance (datos reales) -> motor DASHIA ->
gateway (límites duros) -> Binance (orden real). Esto es lo que correría
en el backend de producción, en un loop o disparado por un scheduler.

No se ejecutó contra la red real desde este sandbox (sin salida a
api.binance.com). Antes de correrlo: crear un archivo .env a partir de
.env.example con una API key de TESTNET (BINANCE_TESTNET=true).
"""
import logging
import time

from dashia_engine import DashiaConfig, run_dashia, RiskConfig

from .config import BinanceCredentials, GatewayLimits
from .client import BinanceConnector
from .gateway import TradingGateway

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("runner")

SYMBOL = "BTC/USDT"
AGENT_ID = "dashia"


def main():
    creds = BinanceCredentials.from_env()  # lee BINANCE_API_KEY / BINANCE_API_SECRET / BINANCE_TESTNET
    connector = BinanceConnector(creds, market_type="spot")

    restrictions = connector.verify_trade_only()
    log.info("Permisos de la API key verificados: %s", restrictions)

    risk_cfg = RiskConfig(plan="WALK", risk_capital_pct=10, sltp_method="PERCENTAGE",
                           stop_loss_pct=2.0, take_profit_pct=6.0)
    gateway = TradingGateway(connector, GatewayLimits(), risk_cfg=risk_cfg,
                              audit_log_path="dashia_audit_log.jsonl")

    dashia_cfg = DashiaConfig(max_bars_back=300, risk=risk_cfg)

    while True:
        try:
            df = connector.get_ohlcv(SYMBOL, timeframe="1h", limit=600)
            signals = run_dashia(df, dashia_cfg)
            last = signals.iloc[-1]
            balance = connector.get_balance()
            equity = balance["total"].get("USDT", 0.0)

            if last["start_long"]:
                gateway.execute_signal(AGENT_ID, "open_long", SYMBOL, equity_usd=equity,
                                        price_hint=last["close"], atr_value=last["atr"])
            elif last["start_short"]:
                gateway.execute_signal(AGENT_ID, "open_short", SYMBOL, equity_usd=equity,
                                        price_hint=last["close"], atr_value=last["atr"])
            elif last["end_long"]:
                gateway.execute_signal(AGENT_ID, "close_long", SYMBOL, equity_usd=equity)
            elif last["end_short"]:
                gateway.execute_signal(AGENT_ID, "close_short", SYMBOL, equity_usd=equity)

        except Exception as e:
            log.exception("Error en el ciclo del runner: %s", e)

        time.sleep(60 * 15)  # revisar cada 15 min — ajustar al timeframe usado


if __name__ == "__main__":
    main()
