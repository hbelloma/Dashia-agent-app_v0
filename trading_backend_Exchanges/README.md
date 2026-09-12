# trading_backend

Ocho paquetes pensados para vivir juntos en el backend:

- `dashia_engine/` — port del algoritmo DASHIA (features, ANN Lorentziano, kernel, backtest)
- `credentials_vault/` — bóveda multiusuario de API keys, cifrado real (envelope encryption)
- `binance_connector/` — conector real a Binance (ccxt, spot+futuros) + gateway de límites duros
- `bybit_connector/` — conector real a Bybit (ccxt, spot+futuros linear) — reutiliza el gateway de Binance
- `weex_connector/` — conector a Weex (ccxt, spot+swap) — SIN verificación automática de permisos, requiere confirmación manual
- `solana_connector/` — conector real a Solana (Jupiter Swap API) + gateway de límites duros
- `agent_sandbox/` — aislamiento real para agentes creados por usuarios (3 capas: DSL restringido, proceso aislado, gateway)
- `market_data/` — capa unificada: pedir "BTC" sin saber de qué exchange viene, con fallback real y caché

Ver el README de cada uno para instalación, setup y limitaciones honestas.

## Instalación conjunta

```bash
pip install ccxt solders solana base58 requests pandas numpy matplotlib pytest cryptography
python -m pytest binance_connector/tests/ bybit_connector/tests/ weex_connector/tests/ \
                  solana_connector/tests/ agent_sandbox/tests/ credentials_vault/tests/ \
                  market_data/tests/ -v
python -m dashia_engine.demo
```

## Cómo encajan las piezas (flujo completo, usuario multiusuario)

```
Usuario conecta sus exchanges desde la app
        │
        ▼
credentials_vault (cifra y guarda cada API key, aislada por user_id)
        │
        ▼
market_data.build_market_data_for_user() -> UnifiedMarketData
(solo con los venues que ESE usuario conectó)
        │
        ▼
Usuario escribe/activa un agente (DASHIA u otro)
        │
        ▼
agent_sandbox (3 capas: DSL restringido → proceso aislado → gateway)
usa UnifiedMarketData.get_price()/get_ohlcv() para alimentar sus decisiones
        │
        ▼
binance_connector.gateway.TradingGateway
(el MISMO gateway sirve para Binance, Bybit Y Weex)
        │
        ▼
Binance / Bybit / Weex / Jupiter (orden real)
```
