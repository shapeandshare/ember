"""Model-server lifecycle: start, stop, restart, status.

Every path that starts the server (``gut-feeling start``, ``gut-feeling restart``,
and MCP autostart) goes through ``start``, so they share model resolution, the pid
file, and the log. ``stop`` only signals the pid this tool recorded, after
confirming it is still a gut-feeling server; it never kills by port or by pattern.
"""

from __future__ import annotations

import os
import signal
import subprocess  # nosec B404
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from . import config, models, paths


def health(host: str, port: int, timeout: float = 2.0) -> dict[str, Any] | None:
    try:
        resp = httpx.get(f"http://{host}:{port}/health", timeout=timeout)
        if resp.status_code != 200:
            return None
        info: dict[str, Any] = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    return info


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


def _is_gut_feeling_server(pid: int) -> bool:
    try:
        command = subprocess.run(  # noqa: S603 - fixed argv, no shell; pid is an int
            ["/bin/ps", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        return False
    return "gut_feeling.server" in command


def tracked_pid(host: str, port: int) -> int | None:
    """The pid recorded by ``start``, if that process is still a gut-feeling server."""
    pid_file = paths.pid_path()
    try:
        pid = int(pid_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None
    if not (_pid_alive(pid) and _is_gut_feeling_server(pid)):
        pid_file.unlink(missing_ok=True)
        return None
    info = health(host, port)
    if info and info.get("pid") not in (None, pid):
        return None
    return pid


def spawn(
    model_dir: Path, host: str, port: int, device: str
) -> subprocess.Popen[bytes]:
    """Launch the model server detached on ``host:port`` and record its pid."""
    env = dict(os.environ)
    env.update(
        {
            "GUT_FEELING_MODEL_DIR": str(model_dir),
            "GUT_FEELING_HOST": host,
            "GUT_FEELING_PORT": str(port),
            "GUT_FEELING_DEVICE": str(device),
            "GUT_FEELING_MAX_LENGTH": str(config.resolve("max_length")),
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
            "HF_HUB_OFFLINE": "1",
        }
    )
    with open(paths.server_log_path(), "ab") as handle:
        proc = subprocess.Popen(
            [sys.executable, "-m", "gut_feeling.server"],
            cwd=str(paths.state_dir()),
            stdout=handle,
            stderr=handle,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
    paths.pid_path().write_text(str(proc.pid))
    return proc


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
    info = health(host, port)
    if info is not None:
        return int(info.get("pid") or 0)

    name = model or config.resolve("model")
    model_dir = models.resolve_dir(name)
    if model_dir is None:
        raise RuntimeError(
            f"model {name!r} is not pulled; run: gut-feeling model pull {name}"
        )

    proc = spawn(model_dir, host, port, device)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_up(host, port):
            return proc.pid
        if proc.poll() is not None:
            raise RuntimeError(
                f"server exited during startup (code {proc.returncode}); "
                f"see {paths.server_log_path()}"
            )
        time.sleep(1.0)
    raise RuntimeError(
        f"server did not become ready within {timeout:.0f}s; "
        f"see {paths.server_log_path()}"
    )


def stop(
    host: str | None = None, port: int | None = None, timeout: float = 15.0
) -> bool:
    host = host or config.resolve("host")
    port = int(port or config.resolve("port"))
    pid = tracked_pid(host, port)
    if pid is None:
        return False
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + timeout
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.2)
    if _pid_alive(pid):
        os.kill(pid, signal.SIGKILL)
    paths.pid_path().unlink(missing_ok=True)
    return True


def restart(
    model: str | None = None,
    host: str | None = None,
    port: int | None = None,
    device: str | None = None,
) -> int:
    stop(host, port)
    return start(model, host, port, device)
