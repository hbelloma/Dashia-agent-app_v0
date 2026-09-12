"""
gateway_bridge.py
==================
Cierra el círculo de las 3 capas del blueprint de seguridad:

  Capa 1 (dsl_interpreter) -> Capa 2 (process_isolation) -> Capa 3 (esto)

Aunque las capas 1 y 2 ya deberían garantizar que el código del agente
no puede hacer nada fuera de "comprar/vender/esperar con tal tamaño",
esta capa asume que las anteriores podrían fallar igual: el agente
nunca ve ni toca el TradingGateway ni las credenciales — solo produce
una Decision dentro del proceso aislado, y ÚNICAMENTE esta función
decide si esa Decision se traduce en una orden real, pasando siempre
por el gateway (whitelist, tamaño máximo, circuit breaker, rate limit —
ver binance_connector/gateway.py y solana_connector/gateway.py).

Funciona con CUALQUIER gateway que tenga el método
execute_signal(agent_id, action, symbol, equity_usd, ...) — tanto
TradingGateway (Binance) como SolanaTradingGateway.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass

from .process_isolation import run_agent_isolated, IsolationLimits, AgentTimeoutError, AgentIsolationError

log = logging.getLogger("gateway_bridge")


@dataclass
class ExecutionOutcome:
    executed: bool
    reason: str
    decision: dict | None = None
    gateway_result: dict | None = None


def _map_action(dsl_action: str, position: str) -> str | None:
    """
    Traduce buy/sell/hold + la posición actual (que YA es parte del
    contexto que el propio agente recibió, ver ALLOWED_VARIABLES) a la
    acción que entiende el gateway. Si la combinación no tiene sentido
    (p.ej. "buy" estando ya long), no se manda nada — no es un error,
    simplemente no hay operación que hacer.
    """
    if dsl_action == "buy":
        if position == "none": return "open_long"
        if position == "short": return "close_short"
        return None  # ya está long, no hay nada que hacer
    if dsl_action == "sell":
        if position == "long": return "close_long"
        if position == "none": return "open_short"  # el gateway la rechaza si el venue no soporta shorts
        return None  # ya está short
    return None  # hold


def evaluate_and_execute(agent_id: str, source: str, symbol: str,
                          indicators: dict, variables: dict, equity_usd: float,
                          gateway, limits: IsolationLimits | None = None) -> ExecutionOutcome:
    """
    Único punto de entrada pensado para usarse desde runner.py de
    binance_connector o solana_connector en vez de llamar al gateway a mano.
    """
    try:
        result = run_agent_isolated(source, indicators, variables, limits)
    except AgentTimeoutError as e:
        log.warning("Agente %s: timeout (%s)", agent_id, e)
        return ExecutionOutcome(executed=False, reason=f"timeout: {e}")
    except AgentIsolationError as e:
        log.warning("Agente %s: error de aislamiento (%s)", agent_id, e)
        return ExecutionOutcome(executed=False, reason=f"aislamiento: {e}")

    if "error" in result:
        # Código rechazado por la Capa 1 (o falló en runtime) — nunca llega
        # al gateway, ni siquiera para que lo rechace él.
        log.info("Agente %s: código rechazado (%s): %s", agent_id, result["type"], result["error"])
        return ExecutionOutcome(executed=False, reason=f"{result['type']}: {result['error']}", decision=result)

    dsl_action = result["action"]
    if dsl_action == "hold":
        return ExecutionOutcome(executed=False, reason="decisión: hold", decision=result)

    gateway_action = _map_action(dsl_action, variables.get("position", "none"))
    if gateway_action is None:
        return ExecutionOutcome(executed=False, reason=f"'{dsl_action}' no aplica con posición actual "
                                                         f"'{variables.get('position')}'", decision=result)

    try:
        gw_result = gateway.execute_signal(agent_id, gateway_action, symbol, equity_usd=equity_usd)
        return ExecutionOutcome(executed=True, reason="ejecutado", decision=result, gateway_result=gw_result)
    except Exception as e:
        # Cualquier rechazo del gateway (GatewayRejection, CircuitBreakerTripped, etc.)
        # aterriza acá — la decisión del agente no se pierde, pero no se ejecutó.
        log.info("Agente %s: gateway rechazó la orden (%s)", agent_id, e)
        return ExecutionOutcome(executed=False, reason=f"gateway rechazó: {e}", decision=result)
