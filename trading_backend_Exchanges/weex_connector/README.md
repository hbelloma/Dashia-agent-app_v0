# weex_connector

Conector a Weex (spot y swap) vía ccxt.

## ⚠️ La limitación real de este conector (léelo antes de usarlo)

A diferencia de Binance y Bybit, **no encontré una forma de verificar
automáticamente que una API key de Weex tenga el permiso de retiro
desactivado.** Busqué en dos lugares:

1. El código fuente de `weex.py` en ccxt (instalado localmente, lo
   inspeccioné de verdad): declara `'withdraw': False` en sus
   capacidades y no tiene ningún endpoint tipo `apiRestrictions` o
   `query-api` como sí tienen Binance y Bybit.
2. Búsqueda de la documentación pública de Weex: no encontré nada
   claro sobre un endpoint de verificación de permisos.

**No hardcodeé una verificación falsa que dijera "todo bien" sin
comprobar nada de verdad** — eso sería peor que no tener nada, porque
daría una falsa sensación de seguridad. En su lugar:

- `verify_trade_only()` **siempre** lanza `PermissionCheckUnavailable`.
- **Ningún método de trading funciona** hasta que se llama a
  `acknowledge_manual_trade_only_check(True)` — que la app solo debe
  invocar después de que un humano miró el dashboard de Weex y confirmó
  a ojo que la key no tiene retiro habilitado.
- Esto se probó de verdad (`tests/test_client.py`,
  `tests/test_gateway_reuse.py`): el bloqueo se respeta incluso cuando
  la orden viene del gateway, no se puede rodear.

Si en algún momento encuentran (o Weex publica) un endpoint real de
verificación de permisos, este es el archivo a actualizar —
`verify_trade_only()` — para que dejar de requerir el ack manual sea
automático en vez de manual.

## Otra limitación real: el modo sandbox de Weex

Leyendo `weex.py` de ccxt: el modo demo/sandbox de Weex **solo cubre
mercados swap** (no spot), y solo soporta `fetchBalance`, `createOrder`,
`fetchPositions`, `fetchClosedOrders` y `fetchCanceledOrders`. No asumir
que probar en sandbox valida el comportamiento en spot — no se puede
probar spot en sandbox con Weex.

## Uso

```python
from weex_connector.config import WeexCredentials
from weex_connector.client import WeexConnector
from binance_connector.gateway import TradingGateway
from binance_connector.config import GatewayLimits

creds = WeexCredentials.from_env()
conn = WeexConnector(creds, market_type="spot")

# Obligatorio antes de poder operar — ver arriba por qué:
conn.acknowledge_manual_trade_only_check(True)  # solo tras confirmar a ojo en el dashboard de Weex

gateway = TradingGateway(conn, GatewayLimits(max_position_usd=500, max_daily_loss_usd=200))
gateway.execute_signal(agent_id="dashia", action="open_long", symbol="BTC/USDT", equity_usd=1000)
```
