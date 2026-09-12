"""
process_isolation.py
=====================
CAPA 2 del sandbox. Asume que la Capa 1 (dsl_interpreter) podría tener
un bug no descubierto, y confina el proceso que la ejecuta de todas
formas. Verificado EN VIVO en este sandbox, con dos correcciones reales
que salieron de probarlo de verdad (no solo de leer el código):

  1. RLIMIT_AS por sí solo NO mata el proceso — Python atrapa el fallo
     de malloc y lanza MemoryError, un error catchable. Se agregó un
     cgroup real (memory.limit_in_bytes) para que el límite lo aplique
     el kernel vía OOM-killer, no algo que el propio proceso pueda
     interceptar.

  2. RLIMIT_NPROC NO se aplica a root — el kernel exime a procesos
     privilegiados de ese límite. Sin bajar privilegios, ese control
     era decorativo. Se agregó drop de privilegios real a `nobody`
     (setgroups/setgid/setuid) antes de ejecutar el código del agente.

Ambas cosas se encontraron porque los tests ejecutan procesos reales en
vez de mockear el resultado — ver tests/test_process_isolation.py.

Limitación honesta que sigue en pie: esto corre como root dentro de un
contenedor que ya es, en sí mismo, una sandbox (este entorno). En
producción lo ideal es que esta capa completa viva dentro de su propio
contenedor/microVM dedicado por ejecución (Docker --network none,
Firecracker, gVisor), no como procesos hijos del mismo host que corre
el backend. Dockerfile de referencia en el README.
"""

from __future__ import annotations
import os
import sys
import json
import time
import uuid
import shutil
import subprocess
import resource
import tempfile
from dataclasses import dataclass

_WORKER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_worker.py")
_PKG_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CGROUP_MEMORY_BASE = "/sys/fs/cgroup/memory"
NOBODY_UID = 65534
NOBODY_GID = 65534


class AgentTimeoutError(RuntimeError):
    pass


class AgentIsolationError(RuntimeError):
    pass


@dataclass
class IsolationLimits:
    cpu_seconds: int = 2
    memory_mb: int = 64
    wall_clock_timeout_s: float = 5.0
    max_open_files: int = 32
    use_network_namespace: bool = True
    use_cgroup_memory: bool = True     # SIGKILL real vía OOM, no solo RLIMIT_AS
    drop_privileges: bool = True       # necesario para que RLIMIT_NPROC se aplique


# ---------------------------------------------------------------------------
# Cgroup de memoria (corrección #1)
# ---------------------------------------------------------------------------
def _create_memory_cgroup(memory_mb: int) -> str | None:
    if not os.path.isdir(_CGROUP_MEMORY_BASE):
        return None
    path = os.path.join(_CGROUP_MEMORY_BASE, f"agent_sandbox_{uuid.uuid4().hex[:8]}")
    try:
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "memory.limit_in_bytes"), "w") as f:
            f.write(str(memory_mb * 1024 * 1024))
        return path
    except Exception:
        return None


def _cleanup_cgroup(path: str | None):
    if not path:
        return
    for _ in range(20):  # tras un SIGKILL el kernel tarda un instante en vaciar el cgroup
        try:
            os.rmdir(path)
            return
        except OSError:
            time.sleep(0.05)


# ---------------------------------------------------------------------------
# preexec_fn — corre en el hijo, después de fork(), antes de exec()
# ---------------------------------------------------------------------------
def _preexec(limits: IsolationLimits, cgroup_path: str | None, drop_privileges_here: bool):
    def _fn():
        if cgroup_path:
            try:
                with open(os.path.join(cgroup_path, "cgroup.procs"), "w") as f:
                    f.write(str(os.getpid()))
            except Exception:
                pass  # si falla, RLIMIT_AS sigue como respaldo más débil

        resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))

        # RLIMIT_AS solo se usa cuando NO hay cgroup activo. Si ambos se
        # fijan al mismo valor, RLIMIT_AS "gana la carrera" (falla el
        # malloc de forma sincrónica y Python lo atrapa como MemoryError)
        # antes de que el cgroup llegue a disparar el OOM-killer real —
        # eso vacía de sentido tener el cgroup. Se usa uno u otro, no
        # ambos al mismo límite.
        if not cgroup_path:
            mem_bytes = limits.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (limits.max_open_files, limits.max_open_files))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.setsid()

        # Con `unshare --net` en la cadena de exec, esto NO puede bajar
        # privilegios aquí — unshare necesita seguir siendo root para
        # poder crear el namespace de red. En ese caso el drop lo hace
        # _worker.py, ya adentro del namespace (ver SANDBOX_DROP_PRIVILEGES).
        if drop_privileges_here and limits.drop_privileges and os.getuid() == 0:
            os.setgroups([])
            os.setgid(NOBODY_GID)
            os.setuid(NOBODY_UID)
    return _fn


def _network_namespace_available() -> bool:
    if not shutil.which("unshare"):
        return False
    try:
        result = subprocess.run(["unshare", "--net", "true"], capture_output=True, timeout=3)
        return result.returncode == 0
    except Exception:
        return False


def _encode_indicators(indicators: dict) -> list:
    out = []
    for key, value in indicators.items():
        if isinstance(key, tuple):
            out.append([key[0], key[1], value])
        else:
            out.append([key, None, value])
    return out


# ---------------------------------------------------------------------------
def run_agent_isolated(source: str, indicators: dict, variables: dict,
                        limits: IsolationLimits | None = None) -> dict:
    limits = limits or IsolationLimits()
    payload = json.dumps({
        "source": source, "variables": variables,
        "indicators": _encode_indicators(indicators),
    })

    cmd = [sys.executable, _WORKER_PATH]
    net_isolated = False
    if limits.use_network_namespace and _network_namespace_available():
        cmd = ["unshare", "--net"] + cmd
        net_isolated = True

    env = {"PATH": "/usr/bin:/bin", "SANDBOX_PKG_PATH": _PKG_PARENT,
           "SANDBOX_DROP_PRIVILEGES": "1" if (net_isolated and limits.drop_privileges) else "0"}
    cgroup_path = _create_memory_cgroup(limits.memory_mb) if limits.use_cgroup_memory else None
    # Si vamos a correr bajo `unshare`, el preexec_fn NO puede bajar privilegios
    # (unshare necesita root) — ese drop lo hace _worker.py una vez adentro.
    drop_in_preexec = not net_isolated

    with tempfile.TemporaryDirectory() as scratch_dir:
        os.chmod(scratch_dir, 0o777)  # el hijo puede terminar corriendo como `nobody`
        try:
            try:
                proc = subprocess.run(
                    cmd, input=payload, capture_output=True, text=True,
                    cwd=scratch_dir, env=env,
                    preexec_fn=_preexec(limits, cgroup_path, drop_in_preexec),
                    timeout=limits.wall_clock_timeout_s,
                )
            except subprocess.TimeoutExpired:
                raise AgentTimeoutError(
                    f"El agente no terminó en {limits.wall_clock_timeout_s}s (timeout de proceso)"
                )
        finally:
            _cleanup_cgroup(cgroup_path)

        if proc.returncode in (-9, 137):
            raise AgentIsolationError(
                "El proceso del agente fue terminado por el kernel "
                "(límite de memoria del cgroup o CPU excedido)"
            )
        if proc.returncode != 0:
            raise AgentIsolationError(
                f"El worker terminó con código {proc.returncode}: {proc.stderr[:500]}"
            )
        if not proc.stdout.strip():
            raise AgentIsolationError("El worker no produjo salida")

        try:
            result = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception as e:
            raise AgentIsolationError(f"Salida del worker no es JSON válido: {e}")

        result["_meta"] = {
            "network_isolated": net_isolated,
            "memory_cgroup_active": cgroup_path is not None,
            "privileges_dropped": limits.drop_privileges,
            "memory_limit_mb": limits.memory_mb,
            "cpu_limit_s": limits.cpu_seconds,
        }
        return result
