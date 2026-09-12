"""
test_dsl_interpreter.py
========================
No son tests de "caso feliz" — cada uno intenta activamente romper el
intérprete con una técnica conocida de escape de sandboxes en Python.
Si alguno de estos pasa (es decir, si el código malicioso SÍ se
ejecuta), es una vulnerabilidad real, no un detalle cosmético.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_sandbox.dsl_interpreter import SafeInterpreter, SandboxSecurityError, SandboxRuntimeError

CTX = dict(indicators={("rsi", 14): 28.4, ("sma", 20): 61000.0, "price": 61200.0},
           variables={"trend": "up", "position": "none"})


def run(source):
    return SafeInterpreter(**CTX).run(source)


# ---------------------------------------------------------------------------
# Caso feliz — confirma que lo legítimo SÍ funciona (si esto falla, el
# sandbox es inútil aunque sea "seguro")
# ---------------------------------------------------------------------------
def test_legitimate_strategy_executes_correctly():
    decision = run('if rsi(14) < 30 and trend == "up":\n    buy(size=risk.default)')
    assert decision.action == "buy"
    assert decision.size == 0.05


def test_no_condition_met_holds():
    decision = run('if rsi(14) > 90:\n    buy(size=risk.default)')
    assert decision.action == "hold"


def test_else_branch_works():
    decision = run('if rsi(14) > 90:\n    buy(size=risk.default)\nelse:\n    sell(size=risk.small)')
    assert decision.action == "sell"
    assert decision.size == 0.02


def test_arithmetic_on_risk_preset_works():
    decision = run('if trend == "up":\n    buy(size=risk.default * 2)')
    assert decision.action == "buy"
    assert abs(decision.size - 0.10) < 1e-9


# ---------------------------------------------------------------------------
# Intentos de escape — CADA UNO debe lanzar SandboxSecurityError
# ---------------------------------------------------------------------------
ATTACK_VECTORS = {
    "import_directo": "import os\nbuy(size=1)",
    "import_from": "from os import system\nbuy(size=1)",
    "dunder_import": "__import__('os').system('id')\nbuy(size=1)",
    "exec_call": "exec('import os')\nbuy(size=1)",
    "eval_call": "buy(size=eval('1'))",
    "open_file": "open('/etc/passwd').read()\nbuy(size=1)",
    "class_mro_escape": "buy(size=().__class__.__mro__[1].__subclasses__())",
    "risk_dunder_class": "buy(size=risk.__class__)",
    "attribute_on_non_risk": "trend.upper()\nbuy(size=1)",
    "lambda_def": "f = lambda: 1\nbuy(size=1)",
    "function_def": "def f():\n    pass\nbuy(size=1)",
    "class_def": "class A:\n    pass\nbuy(size=1)",
    "while_loop": "while True:\n    pass",
    "for_loop": "for i in range(10):\n    pass",
    "list_comprehension": "x = [i for i in range(10)]\nbuy(size=1)",
    "assignment": "x = 5\nbuy(size=x)",
    "fstring": 'buy(size=1)\nx = f"{1+1}"',
    "global_stmt": "global x\nbuy(size=1)",
    "ternary_ifexp": "buy(size=1 if True else 0)",
    "assert_stmt": "assert True\nbuy(size=1)",
    "unknown_function_call": "os_system('id')\nbuy(size=1)",
    "unknown_variable": "buy(size=1)\nif secret_var == 1:\n    sell(size=1)",
    "nested_attribute_in_kwarg": "buy(size=risk.default.__class__.__name__)",
    "string_as_arithmetic_operand": 'buy(size="a" * 999999999)',
    "dict_literal": "d = {}\nbuy(size=1)",
    "starred_expr": "buy(*[1])",
    "kwargs_splat": "buy(**{'size': 1})",
    "walrus_operator": "if (x := rsi(14)) < 30:\n    buy(size=1)",
}


@pytest.mark.parametrize("name,source", ATTACK_VECTORS.items(), ids=list(ATTACK_VECTORS.keys()))
def test_attack_vector_is_rejected(name, source):
    with pytest.raises((SandboxSecurityError, SandboxRuntimeError)):
        run(source)


def test_deeply_nested_expression_does_not_crash_interpreter():
    # Intento de agotar la pila de Python con anidamiento artificial
    nested = "1"
    for _ in range(5000):
        nested = f"({nested}+1)"
    source = f"if {nested} > 0:\n    buy(size=1)"
    with pytest.raises(SandboxSecurityError):
        run(source)  # debe fallar controladamente, no tumbar el proceso


def test_indicator_period_must_be_literal_int():
    with pytest.raises(SandboxRuntimeError):
        run('if rsi(14.5) < 30:\n    sell(size=1)')


def test_unavailable_indicator_raises_runtime_error_not_silent_default():
    with pytest.raises(SandboxRuntimeError):
        run('if rsi(999) < 30:\n    buy(size=1)')  # rsi(999) no está en el contexto
