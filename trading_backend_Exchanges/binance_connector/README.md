# binance_connector

Conector real a Binance (spot y futuros) vía [ccxt](https://github.com/ccxt/ccxt),
con el gateway de límites duros descrito en el blueprint de seguridad.

## ⚠️ Estado honesto de este código

Este sandbox de desarrollo **no tiene salida de red hacia `api.binance.com`**
(confirmado: `x-deny-reason: host_not_allowed`), así que este código:

- ✅ Está escrito contra la API estable y documentada de ccxt 4.x
- ✅ Tiene 10 tests que SÍ corrieron y pasaron aquí — pero usan mocks
  (`FakeConnector` / `unittest.mock`), no la red real de Binance
- ❌ **No se ha probado contra Binance real, ni siquiera testnet**

Antes de acercarle dinero de verdad: correr `runner.py` contra testnet
primero, vigilar los logs y el `dashia_audit_log.jsonl` un tiempo, y
recién después evaluar producción.

## Instalación

```bash
pip install ccxt pandas pytest
cp .env.example .env   # completar con una API key de TESTNET
python -m pytest binance_connector/tests/ -v
```

## Crear la API key correcta en Binance (spot)

1. Binance → API Management → Create API.
2. Habilitar **únicamente**: "Enable Spot & Margin Trading" (y/o "Enable
   Futures" si vas a operar futuros).
3. **NO** habilitar "Enable Withdrawals" — el conector rechaza la key
   automáticamente si la detecta habilitada (`verify_trade_only()`).
4. Activar **whitelist de IP** con la IP fija de tu servidor.
5. Para pruebas, usar primero [Binance Spot Testnet](https://testnet.binance.vision/)
   o el testnet de futuros — son cuentas y claves separadas de producción.

## Uso

```python
from binance_connector.config import BinanceCredentials, GatewayLimits
from binance_connector.client import BinanceConnector
from binance_connector.gateway import TradingGateway
from dashia_engine import RiskConfig

creds = BinanceCredentials.from_env()
conn = BinanceConnector(creds, market_type="spot")
conn.verify_trade_only()  # lanza TradeOnlyViolation si la key puede retirar fondos

gateway = TradingGateway(conn, GatewayLimits(max_position_usd=500, max_daily_loss_usd=200),
                          risk_cfg=RiskConfig(plan="WALK", sltp_method="PERCENTAGE"))

gateway.execute_signal(agent_id="dashia", action="open_long", symbol="BTC/USDT", equity_usd=1000)
```

O correr el loop completo (Binance → DASHIA → gateway → Binance):

```bash
python -m binance_connector.runner
```

## Qué hace el gateway por ti (y qué no)

| Control | Dónde |
|---|---|
| Solo símbolos permitidos | `GatewayLimits.allowed_symbols` |
| Tamaño máx. de posición | `GatewayLimits.max_position_usd` |
| Circuit breaker de pérdida diaria | `GatewayLimits.max_daily_loss_usd` — pausa el agente automáticamente |
| Límite de órdenes/minuto | `GatewayLimits.max_orders_per_minute` |
| Auditoría inmutable | `audit_log.jsonl` (append-only) |
| Verificación de "sin retiro" | `BinanceConnector.verify_trade_only()` |
| **Aislamiento real del código del agente (sandbox/microVM)** | **No incluido aquí** — ver blueprint §4, sigue pendiente |

## Limitaciones conocidas / próximos pasos

- `place_stop_loss` / `place_take_profit` en spot usan órdenes separadas,
  no un OCO real — para producción conviene migrar a
  `create_order` con `type="OCO"` o al endpoint dedicado de Binance.
- El chequeo de permisos (`verify_trade_only`) usa el endpoint de **spot**
  (`sapiGetAccountApiRestrictions`); en futuros conviene además revisar
  manualmente los permisos en el dashboard de Binance.
- Bybit y Weex necesitan su propio conector — la estructura (`client.py`
  + `gateway.py` compartido) está pensada para que el gateway sea el
  mismo y solo cambie la clase de cliente por debajo.
