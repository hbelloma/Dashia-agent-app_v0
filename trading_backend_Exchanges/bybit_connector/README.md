# bybit_connector

Conector real a Bybit (spot y futuros linear/USDT) vía ccxt.

## ⚠️ Estado honesto

Igual que binance_connector: sin salida de red hacia `api.bybit.com`
desde este sandbox. Lo que sí se hizo distinto acá — en vez de asumir
cómo funciona la API de Bybit, se verificó **contra el código fuente de
ccxt instalado localmente** (no es documentación copiada, es inspección
real del paquete):

```bash
python3 -c "import ccxt; ex=ccxt.bybit({}); print(hasattr(ex,'privateGetV5UserQueryApi'))"
# True
```

Eso confirmó el nombre exacto del método para verificar permisos antes
de escribir una sola línea que dependiera de adivinarlo.

## No se duplicó el gateway

`bybit_connector` **no tiene su propio `gateway.py`**. Reutiliza
`binance_connector.gateway.TradingGateway` tal cual — `BybitConnector`
implementa los mismos métodos (`get_last_price`, `place_market_order`,
`place_stop_loss`, `place_take_profit`), así que el gateway con sus
límites duros (whitelist, tope de posición, circuit breaker, rate
limit) funciona sin cambiar una línea. Ver
`tests/test_gateway_reuse.py` — es una prueba real de esto, no una
afirmación.

## Crear la API key correcta en Bybit

1. Bybit → API → Create New Key.
2. Permisos: marcar únicamente **"Contract Trade"** y/o **"Spot Trade"** — dejar **"Withdrawal"** sin marcar.
3. Activar whitelist de IP.
4. `verify_trade_only()` confirma esto automáticamente contra `v5/user/query-api` — si detecta `"Withdraw"` en los permisos de Wallet, rechaza la key.

## Uso

```python
from bybit_connector.config import BybitCredentials
from bybit_connector.client import BybitConnector
from binance_connector.gateway import TradingGateway  # sí, el de binance_connector
from binance_connector.config import GatewayLimits

creds = BybitCredentials.from_env()  # BYBIT_API_KEY / BYBIT_API_SECRET / BYBIT_TESTNET
conn = BybitConnector(creds, market_type="spot")
conn.verify_trade_only()

gateway = TradingGateway(conn, GatewayLimits(max_position_usd=500, max_daily_loss_usd=200))
gateway.execute_signal(agent_id="dashia", action="open_long", symbol="BTC/USDT", equity_usd=1000)
```
