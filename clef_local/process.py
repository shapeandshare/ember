"""Warm-server lifecycle (start/stop/restart/status) without bash/lsof dependencies.

Liveness is proved by the HTTP ``/health`` endpoint (which reports the server PID),
with the pidfile as a fallback. This avoids port-scanning and never touches
processes the CLI did not start.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from . import config, models, paths


def _url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def health(host: str, port: int, timeout: float = 2.0) -> dict | None:
    try:
        resp = httpx.get(f"{_url(host, port)}/health", timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def is_up(host: str, port: int) -> bool:
    return health(host, port) is not None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def server_pid(host: str, port: int) -> int | None:
    info = health(host, port)
    if info and info.get("pid"):
        try:
            return int(info["pid"])
        except (TypeError, ValueError):
            pass
    pid_file = paths.pid_path()
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            return pid if _pid_alive(pid) else None
        except (ValueError, OSError):
            return None
    return None


def _wait_ready(host: str, port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_up(host, port):
            return True
        time.sleep(1.0)
    return False


def start(
    model: str | None = None,
    host: str | None = None,
    port: int | None = None,
    device: str | None = None,
    timeout: float = 300.0,
) -> int:
    host = host or config.resolve("host")
    port = int(port or config.resolve("port"))
    device = device or config.resolve("device")
    if is_up(host, port):
        return server_pid(host, port) or 0

    model_dir = models.resolve_dir(model or config.resolve("model"))
    if model_dir is None:
        raise RuntimeError(
            "model weights not found; run: clef model pull " + (model or config.resolve("model"))
        )

    env = dict(os.environ)
    env.update(
        {
            "CLEF_MODEL_DIR": str(model_dir),
            "CLEF_HOST": host,
            "CLEF_PORT": str(port),
            "CLEF_DEVICE": str(device),
            "CLEF_MAX_LENGTH": str(config.resolve("max_length")),
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
        }
    )
    log = paths.server_log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as handle:
        proc = subprocess.Popen(
            [sys.executable, "-m", "clef_local.server"],
            stdout=handle,
            stderr=handle,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
    paths.pid_path().write_text(str(proc.pid))
    if not _wait_ready(host, port, timeout):
        raise RuntimeError(f"server did not become ready within {timeout:.0f}s; see {log}")
    return proc.pid


def stop(host: str | None = None, port: int | None = None, timeout: float = 15.0) -> bool:
    host = host or config.resolve("host")
    port = int(port or config.resolve("port"))
    pid = server_pid(host, port)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.time() + timeout
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.2)
    if _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    paths.pid_path().unlink(missing_ok=True)
    return True


def restart(model: str | None = None, host: str | None = None, port: int | None = None, device: str | None = None) -> int:
    stop(host, port)
    return start(model, host, port, device)
