"""
test_process_isolation.py
===========================
Procesos reales, no mocks. Dos de estos tests fallaron la primera vez
que se corrieron (memoria vía RLIMIT_AS solo daba MemoryError catchable,
no SIGKILL; NPROC no se aplicaba porque el proceso seguía siendo root) —
eso llevó a las dos correcciones reales en process_isolation.py (cgroup
de memoria + drop de privilegios a `nobody`). Estos tests ahora ejercitan
esa versión corregida.
"""
import os
import sys
import subprocess
import tempfile
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_sandbox.process_isolation import (
    run_agent_isolated, IsolationLimits, AgentTimeoutError, AgentIsolationError,
    _preexec, _network_namespace_available, _create_memory_cgroup, _cleanup_cgroup,
)

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="rlimits/unshare/cgroups son específicos de Linux/POSIX"
)


def _run_isolated_command(code: str, limits: IsolationLimits, timeout=10):
    cgroup_path = _create_memory_cgroup(limits.memory_mb) if limits.use_cgroup_memory else None
    with tempfile.TemporaryDirectory() as scratch:
        os.chmod(scratch, 0o777)
        try:
            return subprocess.run(
                [sys.executable, "-c", code], cwd=scratch,
                preexec_fn=_preexec(limits, cgroup_path, drop_privileges_here=True),
                timeout=timeout, capture_output=True, text=True,
            )
        finally:
            _cleanup_cgroup(cgroup_path)


# ---------------------------------------------------------------------------
# Camino feliz — pipeline completo (DSL + aislamiento)
# ---------------------------------------------------------------------------
def test_legitimate_agent_runs_through_full_isolated_pipeline():
    result = run_agent_isolated(
        source='if rsi(14) < 30 and trend == "up":\n    buy(size=risk.default)',
        indicators={("rsi", 14): 28.4}, variables={"trend": "up", "position": "none"},
    )
    assert result["action"] == "buy"
    assert abs(result["size"] - 0.05) < 1e-9
    assert result["_meta"]["privileges_dropped"] is True


def test_malicious_dsl_is_caught_even_inside_isolated_process():
    result = run_agent_isolated(source="import os\nbuy(size=1)", indicators={}, variables={})
    assert result["type"] == "security"


# ---------------------------------------------------------------------------
# Corrección #1: memoria vía cgroup real (SIGKILL, no MemoryError catchable)
# ---------------------------------------------------------------------------
def test_memory_cgroup_kills_oversized_process_with_sigkill():
    limits = IsolationLimits(memory_mb=64, cpu_seconds=5, wall_clock_timeout_s=10,
                              use_network_namespace=False, use_cgroup_memory=True)
    proc = _run_isolated_command("bytearray(300*1024*1024)", limits)  # 300MB > límite 64MB
    assert proc.returncode in (-9, 137), (
        f"Se esperaba SIGKILL del kernel vía cgroup, código real: {proc.returncode}, "
        f"stderr: {proc.stderr[:200]}"
    )


def test_without_cgroup_only_rlimit_as_gives_catchable_memoryerror():
    # Documenta la diferencia real que motivó la corrección: sin cgroup,
    # el límite existe pero Python lo atrapa como excepción normal.
    limits = IsolationLimits(memory_mb=64, cpu_seconds=5, wall_clock_timeout_s=10,
                              use_network_namespace=False, use_cgroup_memory=False)
    proc = _run_isolated_command(
        "try:\n    bytearray(300*1024*1024)\nexcept MemoryError:\n    print('CAUGHT')",
        limits,
    )
    assert "CAUGHT" in proc.stdout, "RLIMIT_AS solo debería ser catchable, no un SIGKILL"


def test_memory_limit_allows_process_within_budget():
    limits = IsolationLimits(memory_mb=64, cpu_seconds=5, wall_clock_timeout_s=10,
                              use_network_namespace=False)
    proc = _run_isolated_command("bytearray(10*1024*1024); print('ok')", limits)
    assert proc.returncode == 0
    assert "ok" in proc.stdout


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------
def test_cpu_limit_kills_infinite_loop():
    limits = IsolationLimits(memory_mb=64, cpu_seconds=1, wall_clock_timeout_s=10,
                              use_network_namespace=False)
    start = time.time()
    proc = _run_isolated_command("x=0\nwhile True:\n    x+=1", limits)
    elapsed = time.time() - start
    assert proc.returncode in (-9, -24, 137)  # -24 = SIGXCPU antes del SIGKILL final
    assert elapsed < 5, "El límite de CPU debería cortar esto en ~1s, no dejarlo correr"


# ---------------------------------------------------------------------------
# Corrección #2: NPROC solo se aplica si de verdad se bajó de root
# ---------------------------------------------------------------------------
def test_nproc_blocks_fork_when_privileges_are_dropped():
    limits = IsolationLimits(memory_mb=64, cpu_seconds=2, wall_clock_timeout_s=10,
                              use_network_namespace=False, drop_privileges=True)
    proc = _run_isolated_command(
        "import os\ntry:\n    os.fork()\n    print('FORK OK (mal)')\n"
        "except OSError:\n    print('FORK BLOQUEADO')",
        limits,
    )
    assert "FORK BLOQUEADO" in proc.stdout


@pytest.mark.skipif(os.getuid() != 0, reason="este test documenta el comportamiento específico de root")
def test_nproc_does_not_block_fork_without_dropping_privileges():
    # Documenta la corrección: root está exento de RLIMIT_NPROC en Linux.
    limits = IsolationLimits(memory_mb=64, cpu_seconds=2, wall_clock_timeout_s=10,
                              use_network_namespace=False, drop_privileges=False)
    proc = _run_isolated_command(
        "import os\ntry:\n    os.fork()\n    print('FORK OK (root exento)')\n"
        "except OSError:\n    print('FORK BLOQUEADO')",
        limits,
    )
    assert "FORK OK" in proc.stdout, "root está exento de RLIMIT_NPROC — por eso hace falta el drop de privilegios"


# ---------------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _network_namespace_available(),
                     reason="unshare --net no disponible en este entorno")
def test_network_namespace_actually_blocks_network():
    code = "import urllib.request; urllib.request.urlopen('https://pypi.org', timeout=4); print('CONECTO')"
    with tempfile.TemporaryDirectory() as scratch:
        without_ns = subprocess.run([sys.executable, "-c", code], cwd=scratch,
                                     capture_output=True, text=True, timeout=10)
        with_ns = subprocess.run(["unshare", "--net", sys.executable, "-c", code], cwd=scratch,
                                  capture_output=True, text=True, timeout=10)
    assert "CONECTO" in without_ns.stdout, (
        "Este test asume que pypi.org es alcanzable SIN aislar red en este entorno"
    )
    assert "CONECTO" not in with_ns.stdout, "¡La red no debería ser alcanzable dentro del netns!"


def test_wall_clock_timeout_backstop_fires():
    with pytest.raises(AgentTimeoutError):
        run_agent_isolated(
            source='if rsi(14) < 30:\n    buy(size=1)',
            indicators={("rsi", 14): 10}, variables={},
            limits=IsolationLimits(cpu_seconds=1, memory_mb=64, wall_clock_timeout_s=0.001,
                                    use_network_namespace=False),
        )
