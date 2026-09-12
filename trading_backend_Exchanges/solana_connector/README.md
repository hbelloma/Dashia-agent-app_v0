# solana_connector

Conector real a Solana (Jupiter Swap API + RPC) con el mismo gateway de
límites duros que `binance_connector`.

## ⚠️ Estado honesto de este código

Igual que con Binance: este sandbox **no tiene salida de red** hacia
`lite-api.jup.ag` ni `api.mainnet-beta.solana.com` (confirmado,
`x-deny-reason: host_not_allowed`). Este código:

- ✅ Está escrito contra la documentación vigente de Jupiter (verificada
  hoy vía búsqueda — la API migró de `quote-api.jup.ag/v6` a
  `lite-api.jup.ag/swap/v1` / `api.jup.ag/swap/v1`, y el patrón de firma
  con `solders` está confirmado contra ejemplos oficiales)
- ✅ Tiene 15 tests que corrieron y pasaron aquí — la parte de la wallet
  (`test_wallet.py`) es **criptografía real, no mocks**: genera un
  keypair y firma con él de verdad. El resto (Jupiter, RPC) usa fakes
- ❌ No se probó contra Jupiter/Solana reales
- ⚠️ Al escribir los tests, uno falló porque mi primer supuesto sobre el
  formato de `priceImpactPct` era razonable pero incorrecto — quedó
  documentado y corregido en el código, es un buen ejemplo de por qué
  hay que validar esto contra la red real antes de confiar en él

## Arquitectura: por qué una "wallet operativa" y no la Phantom principal

Esto es distinto a como está planteado el conector CEX, y vale la pena
explicarlo: en el blueprint de seguridad dijimos que la Phantom principal
del usuario **nunca** entrega su llave privada. Eso es correcto para
trades manuales (el usuario aprueba cada uno en Phantom). Pero un agente
automatizado operando 24/7 no puede esperar que el usuario apruebe cada
swap a mano — ningún bot real de Solana funciona así (Photon, BullX,
Trojan, Bonkbot, etc. tampoco).

El patrón que sí usa toda la industria:

1. Se genera una **wallet operativa** nueva por agente/usuario
   (`TradingWallet.generate_new()`), cuya llave privada vive cifrada en
   el vault del backend — nunca en el dispositivo del usuario.
2. El usuario deposita un **monto acotado** hacia esa wallet desde su
   Phantom principal (esa transferencia sí la firma Phantom — es una
   pieza de frontend con wallet-adapter, pendiente de construir).
3. El agente opera con esos fondos limitados. Si la wallet operativa se
   ve comprometida, la pérdida máxima es lo que el usuario depositó ahí,
   no el resto de su patrimonio.
4. El usuario retira de vuelta a su Phantom cuando quiera.

Esto es **custodio para ese monto acotado**, no 100% no-custodial como sí
lo es un swap manual firmado directo en Phantom. Es la realidad honesta
de cómo funciona el trading automatizado en Solana — cualquier producto
que te diga lo contrario probablemente esté simplificando.

## Instalación

```bash
pip install solders solana base58 requests
python -m pytest solana_connector/tests/ -v
```

## Generar la wallet operativa

```bash
python -m solana_connector.wallet
```

Guarda el `secret` en el vault del backend (o en `.env` solo para
pruebas locales — nunca en git) como `SOLANA_TRADING_WALLET_SECRET`, y
comparte el `pubkey` con el usuario para que deposite fondos ahí desde
Phantom.

## Variables de entorno

```bash
SOLANA_TRADING_WALLET_SECRET=...   # de wallet.py generate_new()
SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=TU_KEY  # recomendado en vez del público
JUPITER_API_KEY=...    # opcional, gratis en https://portal.jup.ag — mejora rate limit y habilita resolve_mint_by_symbol
```

## Qué NO incluye (a propósito)

- **Shorts.** Jupiter agrega swaps spot. Para shorts reales en Solana
  hace falta un protocolo de perps (Drift, Zeta) — es un conector
  distinto, no este.
- **El flujo de depósito/retiro Phantom → wallet operativa.** Eso es
  frontend (wallet-adapter, firma en el navegador/app), no Python.
- **Mint addresses adivinados.** Solo SOL/USDC/USDT están hardcodeados
  (verificados). Todo lo demás se resuelve en vivo contra la Token API de
  Jupiter (`resolve_mint_by_symbol`) — un mint incorrecto en Solana no
  falla con un error claro, puede simplemente operar el token equivocado,
  así que no vale la pena arriesgar una tabla adivinada.

## Sobre los activos que pediste (BTC, ETH, SOL, LTC, XRP, ARB, XAU)

En Solana, lo nativo y muy líquido es **SOL** y las memecoins. BTC y ETH
existen "wrapped" vía bridges (con bastante menos liquidez que en un
CEX). LTC, XRP y XAU muy probablemente **no** tengan una versión líquida
tradeable en Solana — para esos, lo natural sigue siendo el conector CEX
(`binance_connector`), no este.

## v1 vs v2 — cuál usa el gateway y por qué

Jupiter unificó su API en `swap/v2` (`/order` + `/execute`) como el
camino recomendado — mejor precio (compiten más motores de ruteo,
incluido JupiterZ/RFQ) y Jupiter gestiona el "landing" de la
transacción (reintentos, fees de prioridad optimizados). La diferencia
clave con v1: **v2 exige API key siempre**, no tiene el nivel
`lite-api.jup.ag` gratis y sin registro que sí tiene v1.

`SolanaTradingGateway` elige automáticamente según si hay
`JUPITER_API_KEY` configurada:

| | v1 (legacy) | v2 (recomendado) |
|---|---|---|
| Requiere API key | No (opcional, solo mejora rate limit) | Sí, siempre |
| Quién manda la transacción a la red | Nuestro propio `SolanaRPC` | Jupiter (`/execute`, con reintentos) |
| Motores de ruteo | Solo on-chain (Metis) | Todos (Metis + JupiterZ/RFQ + Dflow + OKX) |
| Calls necesarios | 2 (`/quote` + `/swap`) + envío RPC propio | 1 (`/order`) + `/execute` |

Confirmado contra la documentación oficial (`developers.jup.ag/docs/swap`,
fetcheada directo en vivo, no un resumen de terceros — varios resultados
de búsqueda mezclaban esto con la API de bloXroute, que es un producto
distinto de otra empresa que también usa la palabra "Jupiter"). Lo que
NO se pudo verificar contra una respuesta real (sin salida de red desde
este sandbox): los nombres exactos de un par de campos opcionales del
cuerpo de `/order` más allá de los confirmados
(`inputMint`/`outputMint`/`amount`/`taker`/`slippageBps`). Vale la pena
confirmarlos contra una llamada real antes de producción.

```bash
export JUPITER_API_KEY=...  # gratis con cupo mensual, en https://developers.jup.ag/portal
# sin esto, el gateway sigue funcionando con v1 automáticamente
```

## Uso

```python
from solana_connector.config import SolanaSettings, SolanaGatewayLimits, TradingWalletCredentials
from solana_connector.wallet import TradingWallet
from solana_connector.jupiter_client import JupiterClient
from solana_connector.rpc import SolanaRPC
from solana_connector.gateway import SolanaTradingGateway
from dashia_engine import RiskConfig

settings = SolanaSettings.from_env()
wallet = TradingWallet(TradingWalletCredentials.from_env())
gateway = SolanaTradingGateway(
    JupiterClient(settings), wallet, SolanaRPC(settings),
    SolanaGatewayLimits(max_position_usd=200, max_daily_loss_usd=80),
    risk_cfg=RiskConfig(plan="WALK", sltp_method="PERCENTAGE"),
)

gateway.execute_signal(agent_id="dashia", action="open_long", symbol="SOL", equity_usd=500)
```
