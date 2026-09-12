# market_data

El punto único donde un agente pide "BTC" sin saber (ni le tiene que
importar) si la respuesta viene de Binance, Bybit, Weex o Solana.

## Cómo funciona

```
Agente: get_price("BTC")
        │
        ▼
UnifiedMarketData — mira qué venues tiene conectados ESTE usuario
        │
        ▼
Prueba en orden de prioridad (asset_registry.py): binance → bybit → weex → solana
Si un venue falla (no tiene el par, error de red, no está conectado),
pasa al siguiente — no se cae, no hace falta que la tabla de prioridad
sea perfecta.
        │
        ▼
Devuelve PriceQuote(asset, venue, price, symbol_used, fetched_at)
+ caché de 5s por defecto para no golpear rate limits si varios
agentes preguntan lo mismo casi al mismo tiempo
```

## No es código nuevo de conexión — es una capa sobre lo que ya existe

`CEXMarketDataProvider` no habla con ningún exchange directo: envuelve
el `BinanceConnector`/`BybitConnector`/`WeexConnector` que ya estaban
construidos y probados. Funciona con los tres exactamente por la misma
razón que permitió reutilizar `TradingGateway` entre ellos: comparten
`get_last_price()` y `get_ohlcv()`.

## Solana ya tiene histórico real — Birdeye + GeckoTerminal, con fallback

Jupiter (la API que usa `solana_connector`) no tiene ni va a tener un
endpoint de velas — no es su negocio, es un agregador de swaps. Para
resolver esto investigué cómo lo hacen las herramientas reales del
ecosistema antes de elegir:

### Cómo lo hace Photon

**No se pudo confirmar** — Photon es código cerrado y no publica su
arquitectura de datos. Lo que sí se sabe con certeza: usa **TradingView**
para renderizar sus gráficos (mismo motor de charting que usa
GeckoTerminal para el suyo), agrega liquidez de Raydium/Pump.fun/Meteora
directo on-chain, y su ventaja de velocidad (ejecución sub-300ms) viene
de una wallet embebida que evita el popup de Phantom en cada trade — eso
es un tema de *ejecución*, no necesariamente de *dónde saca las velas
del gráfico*. No hay forma honesta de confirmar más que esto sin acceso
a su código.

### Birdeye vs. GeckoTerminal — comparación real

| | Birdeye | GeckoTerminal (CoinGecko on-chain) |
|---|---|---|
| Requiere API key | Sí, incluso gratis | No, para lo básico ("Keyless Public API") |
| Límite gratis | 30K compute units/mes, **1 req/seg** | **30 req/min** (~0.5 req/seg) |
| Pedir OHLCV por dirección de token directo | Sí (`base_quote`, con el mint del activo y de USDC) | Sí (`/tokens/{address}/ohlcv/...`, usa el pool más líquido automático) |
| Granularidad gratis | 1 minuto | 1 minuto |
| Tiempo real / push | WebSocket con velas de **1s/15s/30s** — pero plan **Business (pago)** | No — solo REST, sin WebSocket |
| Especialización en Solana | Alta — nació enfocado en Solana, + seguridad de tokens y analítica de holders | Media — 200+ redes, Solana es una más |
| Costo de esta comparación | Confirmado contra `docs.birdeye.so` | Confirmado contra `docs.coingecko.com` (el producto on-chain de CoinGecko) |

**Conclusión y lo que implementé:** para precisión, ambos indexan
directo on-chain (no derivan de un CEX), así que la calidad del dato
base es comparable — Birdeye tiene más profundidad Solana-específica.
Para latencia gratis, Birdeye tiene el límite de requests más generoso
(1/seg vs 0.5/seg). Para latencia de verdad tipo Photon (velas de
segundos, push en vivo), **ninguno de los dos es gratis** — hace falta
el plan Business de Birdeye.

Por eso `SolanaMarketDataProvider.get_ohlcv()` prueba **Birdeye primero,
GeckoTerminal como respaldo gratis** — mismo patrón de fallback que ya
usa `UnifiedMarketData` entre exchanges. Si no se configura
`BIRDEYE_API_KEY`, funciona igual solo con GeckoTerminal (gratis, sin
setup). Si se quiere la latencia de segundos real, hay que pagar el plan
Business de Birdeye y cambiar a su WebSocket — eso no está implementado
acá, sería la Fase 2 de esto si el producto lo necesita.

```bash
export BIRDEYE_API_KEY=...   # opcional — si falta, usa solo GeckoTerminal
```


## `LTC`, `XRP`, `XAU` — no soportados vía Solana, a propósito

`asset_registry.NOT_LIQUID_ON_SOLANA` bloquea estos tres desde
`SolanaMarketDataProvider.get_price()` sin siquiera intentar la red —
mismo hallazgo ya documentado en `solana_connector/README.md`.

## De la bóveda de un usuario a datos listos para su agente

```python
from credentials_vault.store import CredentialsVault
from market_data.vault_bridge import build_market_data_for_user

vault = CredentialsVault(db_path="vault.db")
umd = build_market_data_for_user(vault, user_id="user_123")

quote = umd.get_price("BTC")           # prueba los venues que ESE usuario conectó, en orden
print(quote.venue, quote.price)

df = umd.get_ohlcv("ETH", timeframe="1h", limit=300)  # para alimentar dashia_engine.run_dashia()
```

Si el usuario solo conectó Solana, `umd.available_venues == ["solana"]`
y pedir `get_ohlcv("BTC")` falla con `NoVenueAvailableError` — no
inventa una respuesta.

## Conectar esto con el motor DASHIA

El DataFrame que devuelve `get_ohlcv()` ya viene en el formato exacto
que espera `dashia_engine.run_dashia(df, cfg)` — columnas
open/high/low/close/volume indexadas por tiempo. Es el mismo formato
que ya usaban `binance_connector.runner.py` y `solana_connector.runner.py`
por separado; esta capa es lo que les faltaba para no tener que elegir
un exchange de antemano.
