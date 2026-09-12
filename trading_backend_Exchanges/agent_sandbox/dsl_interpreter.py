"""
dsl_interpreter.py
===================
CAPA 1 del sandbox de agentes: el código que escribe el usuario NUNCA se
ejecuta como Python real (nada de eval/exec/compile-and-run). Se parsea
con `ast.parse` y se camina el árbol a mano, aceptando SOLO los tipos de
nodo, nombres y llamadas de una lista blanca explícita. Cualquier otra
cosa — imports, atributos arbitrarios, funciones, clases, loops,
comprensiones, f-strings, etc. — se rechaza ANTES de ejecutar nada.

Diseño deliberado: es lista blanca (default-deny), no lista negra
(default-allow). Intentar enumerar "todo lo peligroso" en Python real
está condenado a tener huecos; enumerar "las 20 cosas que sí se pueden
hacer" es una superficie de ataque que se puede razonar por completo.

Esta es la única capa que garantiza algo por construcción. Las capas 2
(aislamiento de proceso) y 3 (gateway) son defensa adicional, no el
único punto de falla.
"""

from __future__ import annotations
import ast
from dataclasses import dataclass, field
from typing import Any


class SandboxSecurityError(Exception):
    """El código del agente intentó usar algo fuera de la lista blanca."""


class SandboxRuntimeError(Exception):
    """El código es válido pero falló en tiempo de evaluación (p.ej. indicador no disponible)."""


# ---------------------------------------------------------------------------
# Lista blanca — esto ES la superficie de ataque completa, a propósito
# ---------------------------------------------------------------------------
INDICATOR_FUNCS = {"rsi", "sma", "ema"}          # requieren 1 argumento entero (periodo)
ZERO_ARG_FUNCS = {"price", "volume"}              # sin argumentos
ACTION_FUNCS = {"buy", "sell", "hold"}            # producen la decisión final
ALLOWED_CALL_NAMES = INDICATOR_FUNCS | ZERO_ARG_FUNCS | ACTION_FUNCS

ALLOWED_VARIABLES = {"trend", "position"}         # Name loads permitidos fuera de una llamada
RISK_PRESETS = {"default": 0.05, "small": 0.02, "large": 0.10}  # risk.xxx -> fracción del equity

ALLOWED_COMPARE_OPS = (ast.Lt, ast.Gt, ast.LtE, ast.GtE, ast.Eq, ast.NotEq)
ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
ALLOWED_BOOLOPS = (ast.And, ast.Or)


@dataclass
class Decision:
    action: str = "hold"          # "buy" | "sell" | "hold"
    size: float = 0.0             # fracción del equity, 0..1
    reasons: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validación — se camina TODO el árbol antes de ejecutar nada, incluidas
# ramas que no se vayan a tomar esta vez (un `if False: os.system(...)`
# se rechaza igual, no solo cuando le tocaría ejecutarse).
# ---------------------------------------------------------------------------
def _validate(node: ast.AST, ctx: str = "stmt") -> None:
    if isinstance(node, ast.Module):
        for stmt in node.body:
            _validate(stmt, "stmt")
        return

    if isinstance(node, ast.If):
        _validate(node.test, "expr")
        for stmt in node.body:
            _validate(stmt, "stmt")
        for stmt in node.orelse:
            _validate(stmt, "stmt")
        return

    if isinstance(node, ast.Expr):
        _validate(node.value, "expr")
        return

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_CALL_NAMES:
            raise SandboxSecurityError(
                f"Llamada no permitida: {getattr(node.func, 'id', ast.dump(node.func))}"
            )
        for arg in node.args:
            _validate(arg, "expr")
        for kw in node.keywords:
            if kw.arg is None:
                raise SandboxSecurityError("No se permite **kwargs")
            _validate(kw.value, "expr")
        return

    if isinstance(node, ast.Attribute):
        if not (isinstance(node.value, ast.Name) and node.value.id == "risk"
                and node.attr in RISK_PRESETS):
            raise SandboxSecurityError(f"Acceso a atributo no permitido: .{node.attr}")
        return

    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or not isinstance(node.ops[0], ALLOWED_COMPARE_OPS):
            raise SandboxSecurityError("Operador de comparación no permitido")
        _validate(node.left, "expr")
        _validate(node.comparators[0], "expr")
        return

    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, ALLOWED_BOOLOPS):
            raise SandboxSecurityError("Operador booleano no permitido")
        for v in node.values:
            _validate(v, "expr")
        return

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ast.Not):
            raise SandboxSecurityError("Operador unario no permitido")
        _validate(node.operand, "expr")
        return

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, ALLOWED_BINOPS):
            raise SandboxSecurityError("Operador aritmético no permitido")
        _validate(node.left, "expr")
        _validate(node.right, "expr")
        return

    if isinstance(node, ast.Name):
        if ctx == "expr" and node.id not in ALLOWED_VARIABLES:
            raise SandboxSecurityError(f"Variable no permitida: {node.id}")
        return

    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float, str, bool)) or isinstance(node.value, complex):
            raise SandboxSecurityError(f"Constante no permitida: {node.value!r}")
        return

    # Cualquier otro tipo de nodo — Import, FunctionDef, Lambda, ClassDef,
    # For, While, With, Try, Subscript, ListComp/SetComp/DictComp/GeneratorExp,
    # JoinedStr (f-strings), Starred, Global, Assign, Return, Yield, etc. —
    # se rechaza explícitamente. Lista blanca, no lista negra.
    raise SandboxSecurityError(f"Construcción de lenguaje no permitida: {type(node).__name__}")


# ---------------------------------------------------------------------------
# Evaluación — solo corre después de que _validate() aprobó TODO el árbol
# ---------------------------------------------------------------------------
def _eval(node: ast.AST, indicators: dict, variables: dict) -> Any:
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        return variables.get(node.id)

    if isinstance(node, ast.Attribute):
        return RISK_PRESETS[node.attr]

    if isinstance(node, ast.Compare):
        left = _eval(node.left, indicators, variables)
        right = _eval(node.comparators[0], indicators, variables)
        op = node.ops[0]
        if isinstance(op, ast.Lt): return left < right
        if isinstance(op, ast.Gt): return left > right
        if isinstance(op, ast.LtE): return left <= right
        if isinstance(op, ast.GtE): return left >= right
        if isinstance(op, ast.Eq): return left == right
        if isinstance(op, ast.NotEq): return left != right

    if isinstance(node, ast.BoolOp):
        values = [_eval(v, indicators, variables) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)

    if isinstance(node, ast.UnaryOp):
        return not _eval(node.operand, indicators, variables)

    if isinstance(node, ast.BinOp):
        l = _eval(node.left, indicators, variables)
        r = _eval(node.right, indicators, variables)
        if not isinstance(l, (int, float)) or not isinstance(r, (int, float)) \
                or isinstance(l, bool) or isinstance(r, bool):
            # ast permite BinOp entre cualquier tipo (p.ej. "a" * 999999999 repite
            # el string) — el árbol por sí solo no distingue tipos, así que se
            # valida en tiempo de evaluación, no alcanza con la lista blanca de nodos.
            raise SandboxRuntimeError("Operación aritmética solo permitida entre números")
        if isinstance(node.op, ast.Add): return l + r
        if isinstance(node.op, ast.Sub): return l - r
        if isinstance(node.op, ast.Mult): return l * r
        if isinstance(node.op, ast.Div):
            if r == 0:
                raise SandboxRuntimeError("División por cero en el código del agente")
            return l / r

    if isinstance(node, ast.Call):
        name = node.func.id
        args = [_eval(a, indicators, variables) for a in node.args]
        kwargs = {kw.arg: _eval(kw.value, indicators, variables) for kw in node.keywords}

        if name in INDICATOR_FUNCS:
            period = args[0] if args else kwargs.get("period")
            if not isinstance(period, int) or isinstance(period, bool):
                raise SandboxRuntimeError(f"{name}() requiere un periodo entero")
            key = (name, period)
            if key not in indicators:
                raise SandboxRuntimeError(
                    f"Indicador {name}({period}) no disponible en el contexto de mercado"
                )
            return indicators[key]

        if name in ZERO_ARG_FUNCS:
            if name not in indicators:
                raise SandboxRuntimeError(f"{name}() no disponible en el contexto de mercado")
            return indicators[name]

        if name in ACTION_FUNCS:
            size = kwargs.get("size", args[0] if args else 0.0)
            if name != "hold" and not isinstance(size, (int, float)):
                raise SandboxRuntimeError(f"{name}(size=...) requiere un tamaño numérico")
            return ("__ACTION__", name, float(size) if name != "hold" else 0.0)

    raise SandboxSecurityError(f"Nodo no evaluable: {type(node).__name__}")  # no debería llegar aquí


def _exec_stmts(stmts: list[ast.stmt], indicators: dict, variables: dict, reasons: list) -> Decision | None:
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            if _eval(stmt.test, indicators, variables):
                reasons.append(f"if verdadero en línea {stmt.lineno}")
                result = _exec_stmts(stmt.body, indicators, variables, reasons)
                if result is not None:
                    return result
            else:
                result = _exec_stmts(stmt.orelse, indicators, variables, reasons)
                if result is not None:
                    return result
        elif isinstance(stmt, ast.Expr):
            value = _eval(stmt.value, indicators, variables)
            if isinstance(value, tuple) and value and value[0] == "__ACTION__":
                _, action, size = value
                size = max(0.0, min(1.0, size))  # clamp defensivo, aunque el gateway también valida
                return Decision(action=action, size=size, reasons=list(reasons))
    return None


class SafeInterpreter:
    """
    Uso:
        interp = SafeInterpreter(indicators={("rsi", 14): 28.4, "price": 61200.0},
                                  variables={"trend": "up", "position": "none"})
        decision = interp.run(source_code)
    """
    def __init__(self, indicators: dict, variables: dict):
        self.indicators = indicators
        self.variables = variables

    def run(self, source: str) -> Decision:
        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError as e:
            raise SandboxSecurityError(f"Error de sintaxis: {e}") from e

        try:
            _validate(tree)  # sobre TODO el árbol, antes de ejecutar cualquier cosa
            reasons: list = []
            decision = _exec_stmts(tree.body, self.indicators, self.variables, reasons)
        except RecursionError:
            # Árbol de expresiones anidado a propósito para agotar la pila de
            # Python (p.ej. "1+(1+(1+(1+...)))" miles de veces). _validate y
            # _exec_stmts son recursivos, así que esto es una vía de ataque real
            # contra el intérprete mismo, no contra lo que ejecuta.
            raise SandboxSecurityError("Expresión demasiado anidada (posible intento de agotar la pila)")

        return decision if decision is not None else Decision(action="hold", size=0.0,
                                                                reasons=["ninguna condición se cumplió"])
