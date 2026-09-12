# agent_sandbox

La pieza de seguridad que faltaba del blueprint (§4): aislamiento real
para que "cualquiera pueda crear su propio agente" no signifique
"cualquiera puede correr código arbitrario con acceso a dinero real".

## Las 3 capas

```
Código del agente (DSL, no Python real)
        │
        ▼
CAPA 1 — dsl_interpreter.py
Lista blanca sobre el AST. No hay eval/exec. Si no es exactamente
if/comparaciones/and-or-not/llamadas a rsi·sma·ema·buy·sell·hold,
se rechaza — incluso en ramas que no se iban a ejecutar esta vez.
        │
        ▼
CAPA 2 — process_isolation.py + _worker.py
Por si la Capa 1 tuviera un bug no descubierto: proceso aparte,
sin red (namespace), memoria limitada (cgroup, SIGKILL real),
CPU limitada (rlimit, SIGKILL real), sin poder hacer fork,
corriendo como `nobody` en vez de root.
        │
        ▼
CAPA 3 — gateway_bridge.py
Por si las capas 1 y 2 fallaran igual: la decisión del agente
NUNCA toca las credenciales ni el exchange directo — pasa por
TradingGateway (whitelist, tope de posición, circuit breaker,
rate limit — ver binance_connector/ y solana_connector/).
```

Ninguna capa es "la que importa" — es defensa en profundidad de verdad:
cada una se probó de forma independiente, asumiendo que las otras dos
podrían no existir.

## Qué se verificó EN VIVO en este sandbox (no es documentación teórica)

51 tests, todos corridos de verdad acá mismo — vale la pena leer
`tests/` porque el camino para llegar a esta versión importa tanto como
el resultado:

- **26 vectores de ataque reales** contra el intérprete (imports,
  `__class__.__mro__`, `eval`/`exec`, comprensiones, fugas por atributos,
  bombas de memoria por repetición de strings, anidamiento para agotar
  la pila de Python) — todos rechazados.
- **Un cgroup de memoria mata de verdad un proceso que se pasa** (SIGKILL,
  código de salida 137) — y se comprobó, probando también lo contrario,
  que `RLIMIT_AS` solo no alcanza: Python lo atrapa como `MemoryError`,
  una excepción normal, no una muerte forzada. Se corrigió para que el
  cgroup sea la barrera dura y no compita con un límite más blando al
  mismo valor.
- **Un límite de CPU mata de verdad un loop infinito** en ~1 segundo.
- **`root` está exento de `RLIMIT_NPROC`** — se comprobó que sin bajar
  privilegios a un usuario real (`nobody`), el límite de "no puedas
  hacer fork" no se aplicaba. Se corrigió bajando privilegios de verdad,
  y ahora sí se aplica.
- **Un namespace de red deja al proceso sin poder conectarse a nada** —
  probado en A/B: el mismo comando, con y sin `unshare --net`, contra un
  dominio que SÍ es alcanzable desde este entorno (pypi.org).
- **Una decisión maliciosa o en `hold` nunca llega a tocar el gateway.**

Dos de estas correcciones (memoria y privilegios) salieron de que el
primer intento **falló** al correr los tests — quedó así a propósito en
el historial de este chat en vez de limpiarlo, porque es la prueba de
que se verificó de verdad y no se documentó "por que debería funcionar".

## Lo que esto NO reemplaza (limitación honesta)

Todo lo anterior corrió como root dentro de un contenedor que **ya es**,
en sí mismo, una sandbox (este entorno de desarrollo). Aislar procesos
dentro del mismo kernel/host (rlimits + cgroups + namespaces) es una
capa real y vale la pena tenerla, pero no es lo mismo que aislamiento
a nivel de kernel completo. Para un sistema multiusuario con dinero real
en producción, esta Capa 2 debería vivir dentro de:

- **Docker con endurecimiento real** (mínimo viable, ver Dockerfile abajo), o
- **gVisor** (`runsc`) como runtime de contenedor, que intercepta las
  syscalls y da una capa extra de aislamiento aunque el código adentro
  se comporte como root, o
- **Firecracker** (microVMs, lo que usa AWS Lambda) para aislamiento a
  nivel de hardware-virtualizado por ejecución — la opción recomendada
  en el blueprint original si el volumen de agentes lo justifica.

Ese salto (de "procesos aislados en el mismo host" a "microVM por
ejecución") es trabajo de infraestructura real, no algo que se resuelva
con más código Python — necesita un host con KVM y orquestación
(Firecracker + jailer, o un servicio gestionado que ya lo dé).

## Dockerfile de referencia para el despliegue real

```dockerfile
FROM python:3.12-slim
RUN useradd --no-create-home --shell /usr/sbin/nologin sandboxuser
WORKDIR /app
COPY agent_sandbox/ ./agent_sandbox/
RUN pip install --no-cache-dir pandas numpy
USER sandboxuser
ENTRYPOINT ["python3", "-m", "agent_sandbox._worker"]
```

Correrlo con:
```bash
docker run --rm -i \
  --network none \
  --memory=64m --memory-swap=64m \
  --cpus=0.5 \
  --pids-limit=16 \
  --read-only --tmpfs /tmp:size=8m \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  agent-sandbox-worker < payload.json
```

Esto es estrictamente más fuerte que lo que hace `process_isolation.py`
hoy (que comparte el kernel del host) — es el paso natural siguiente
cuando esto salga de prototipo.

## Uso

```python
from agent_sandbox.gateway_bridge import evaluate_and_execute
from agent_sandbox.process_isolation import IsolationLimits

outcome = evaluate_and_execute(
    agent_id="dashia",
    source='if rsi(14) < 30 and trend == "up":\n    buy(size=risk.default)',
    symbol="BTC/USDT",
    indicators={("rsi", 14): 28.4},
    variables={"trend": "up", "position": "none"},
    equity_usd=1000,
    gateway=mi_trading_gateway,  # TradingGateway o SolanaTradingGateway
    limits=IsolationLimits(cpu_seconds=2, memory_mb=64, wall_clock_timeout_s=5),
)
print(outcome.executed, outcome.reason)
```

## El DSL que sí se puede escribir

```
if rsi(14) < 30 and trend == "up":
    buy(size=risk.default)
if rsi(14) > 70:
    sell(size=risk.small)
```

Funciones disponibles: `rsi(n)`, `sma(n)`, `ema(n)`, `price()`, `volume()`,
`buy(size=...)`, `sell(size=...)`, `hold()`. Variables: `trend`, `position`.
Tamaños: `risk.default` (5%), `risk.small` (2%), `risk.large` (10%) —
fracción del equity, igual que los planes COOK/WALK/HAWK/ALLIN de DASHIA.
Nada más existe en este lenguaje — esa es la garantía de seguridad, no
una limitación de la versión 1.
