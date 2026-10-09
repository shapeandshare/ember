"""Model-server lifecycle: start, stop, restart, status.

Every path that starts the server (``ember start``, ``ember restart``,
and MCP autostart) goes through ``start``, so they share model resolution, the pid
file, and the log. ``stop`` only signals the pid this tool recorded, after
confirming it is still an ember server; it never kills by port or by pattern.
"""

from __future__ import annotations

import fcntl
import logging
import logging.handlers
import os
import signal
import subprocess  # nosec B404
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .. import models
from ..cfg import config, paths
from . import hosted

_LOG = logging.getLogger(__name__)


def health(host: str, port: int, timeout: float = 2.0) -> dict[str, Any] | None:
    """Query the model server's ``/health`` endpoint.

    Parameters
    ----------
    host : str
        Model server host.
    port : int
        Model server port.
    timeout : float, optional
        Request timeout in seconds. Defaults to ``2.0``.

    Returns
    -------
    dict[str, Any] | None
        The parsed JSON health body, or ``None`` if the request fails or
        returns a non-200 status.
    """
    try:
        resp = httpx.get(f"http://{host}:{port}/health", timeout=timeout)
        if resp.status_code != 200:
            return None
        info: dict[str, Any] = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    return info


def is_up(host: str, port: int) -> bool:
    """Return whether the model server answers ``/health`` at ``host:port``.

    Parameters
    ----------
    host : str
        Model server host.
    port : int
        Model server port.

    Returns
    -------
    bool
        ``True`` if ``health`` returns a body, ``False`` otherwise.
    """
    return health(host, port) is not None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _is_ember_server(pid: int) -> bool:
    try:
        # Fixed argv, no shell expansion; pid is an int — not untrusted input.
        command = subprocess.run(  # noqa: S603
            ["/bin/ps", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        return False
    return "ember.serving.server" in command


def tracked_pid(host: str, port: int) -> int | None:
    """Return the pid recorded by ``start``, if it is still an ember server.

    Parameters
    ----------
    host : str
        Model server host, used to cross-check the pid against ``/health``.
    port : int
        Model server port, used to cross-check the pid against ``/health``.

    Returns
    -------
    int | None
        The tracked pid, or ``None`` if there is no pid file, the recorded
        process is gone or is not an ember server, or a running server at
        ``host:port`` reports a different pid.
    """
    pid_file = paths.pid_path()
    try:
        pid = int(pid_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None
    if not (_pid_alive(pid) and _is_ember_server(pid)):
        pid_file.unlink(missing_ok=True)
        return None
    info = health(host, port)
    if info and info.get("pid") not in (None, pid):
        return None
    return pid


_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file (D-004)
_LOG_BACKUP_COUNT = 3  # keep server.log, server.log.1, server.log.2, server.log.3


def spawn(
    model_dir: Path, host: str, port: int, device: str
) -> subprocess.Popen[bytes]:
    """Launch the model server detached on ``host:port`` and record its pid."""
    env = dict(os.environ)
    env.update(
        {
            "EMBER_MODEL_DIR": str(model_dir),
            "EMBER_HOST": host,
            "EMBER_PORT": str(port),
            "EMBER_DEVICE": str(device),
            "EMBER_MAX_LENGTH": str(config.resolve("max_length")),
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
            "HF_HUB_OFFLINE": "1",
        }
    )
    # D-004: use a RotatingFileHandler so server.log is capped at 10 MB with
    # 3 backups (server.log.1 … server.log.3).  We borrow its stream for the
    # Popen stdout/stderr file descriptor; the handler is then closed in the
    # parent so only the child process writes to the descriptor.
    log_path = paths.server_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        str(log_path),
        mode="ab",
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding=None,
        delay=False,
    )
    handle = handler.stream
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "ember.serving.server"],
            cwd=str(paths.state_dir()),
            stdout=handle,
            stderr=handle,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
    finally:
        handler.close()
    pid_path = paths.pid_path()
    tmp = pid_path.with_suffix(".tmp")
    tmp.write_text(str(proc.pid), encoding="utf-8")
    os.replace(tmp, pid_path)
    return proc


def start(
    model: str | None = None,
    host: str | None = None,
    port: int | None = None,
    device: str | None = None,
    timeout: float = 300.0,
) -> int:
    """Start the model server if it is not already running, and wait for it.

    Every start path (``ember start``, ``ember restart``, and MCP autostart)
    goes through this function, so they share model resolution, the pid
    file, and the log.

    Parameters
    ----------
    model : str | None, optional
        Model name to run; defaults to the resolved config value.
    host : str | None, optional
        Host to bind; defaults to the resolved config value.
    port : int | None, optional
        Port to bind; defaults to the resolved config value.
    device : str | None, optional
        Device to run on (``"auto"``, ``"mps"``, or ``"cpu"``); defaults to
        the resolved config value.
    timeout : float, optional
        Seconds to wait for the server to become healthy. Defaults to
        ``300.0``.

    Returns
    -------
    int
        The model server's pid, whether newly spawned or already running.

    Raises
    ------
    RuntimeError
        If the model is not pulled, the server process exits during
        startup, or it does not become healthy within ``timeout``; or if
        ``EMBER_MODEL_S3_URI`` is malformed or its download fails (see
        :mod:`ember.serving.hosted`). The hosted check runs here, in the
        parent process, before spawning the server subprocess, so a
        misconfiguration fails fast rather than spawning a child that then
        crashes during its own startup.
    """
    host = host or config.resolve("host")
    port = int(port or config.resolve("port"))
    device = device or config.resolve("device")
    info = health(host, port)
    if info is not None:
        return int(info.get("pid") or 0)

    hosted_source = hosted.resolve()
    model_dir: Path | None
    if hosted_source is not None:
        model_dir = hosted_source.model_dir
    else:
        name = model or config.resolve("model")
        model_dir = models.resolve_dir(name)
        if model_dir is None:
            raise RuntimeError(
                f"model {name!r} is not pulled; run: ember model pull {name}"
            )

    # D-005: serialize concurrent autostart calls with a file lock so two MCP
    # processes that both pass the is_up() check above cannot race to spawn
    # two server processes on the same port.
    lock_path = paths.pid_path().with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as _lock_fh:
        fcntl.flock(_lock_fh, fcntl.LOCK_EX)
        # Re-check after acquiring the lock; a concurrent caller may have
        # already spawned and the server may now be healthy.
        if is_up(host, port):
            recheck = health(host, port)
            return int((recheck or {}).get("pid") or 0)
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


def _append_audit_log(message: str) -> None:
    """Append a timestamped audit entry to the server log.

    Best-effort: if the log write fails (e.g. the log directory is missing or
    read-only), a warning is logged and the caller continues.  A
    broken log directory must never prevent stopping a runaway server.

    Parameters
    ----------
    message : str
        The audit message to append (without timestamp; one is prepended).
    """
    ts = datetime.now(tz=UTC).isoformat(timespec="seconds")
    line = f"{ts} {message}\n"
    try:
        with open(paths.server_log_path(), "ab") as fh:
            fh.write(line.encode())
    except OSError as exc:
        _LOG.warning("could not write audit log: %s", exc)


def stop(
    host: str | None = None, port: int | None = None, timeout: float = 15.0
) -> bool:
    """Stop the model server tracked by the pid file, if it is running.

    Signals only the pid recorded by ``start``, after confirming it is
    still an ember server; it never kills by port or by process pattern.

    Before sending ``SIGTERM`` an audit entry is appended to
    ``paths.server_log_path()`` recording the action and pid.  If the process
    does not exit within ``timeout`` seconds and ``SIGKILL`` is sent, a second
    audit entry is appended.  No entry is written when no server is tracked
    (the early ``return False`` path).  Audit writes are best-effort: an
    ``OSError`` on the log append is reported to stderr but does not prevent
    the signal from being sent.

    Parameters
    ----------
    host : str | None, optional
        Host used to cross-check the tracked pid; defaults to the resolved
        config value.
    port : int | None, optional
        Port used to cross-check the tracked pid; defaults to the resolved
        config value.
    timeout : float, optional
        Seconds to wait for a graceful shutdown before sending
        ``SIGKILL``. Defaults to ``15.0``.

    Returns
    -------
    bool
        ``True`` if a tracked server was signaled, ``False`` if none was
        running.
    """
    host = host or config.resolve("host")
    port = int(port or config.resolve("port"))
    pid = tracked_pid(host, port)
    if pid is None:
        return False
    _append_audit_log(f"stop: signaling pid={pid}")
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + timeout
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.2)
    if _pid_alive(pid):
        _append_audit_log(f"stop: escalating to SIGKILL for pid={pid}")
        os.kill(pid, signal.SIGKILL)
    paths.pid_path().unlink(missing_ok=True)
    return True


def restart(
    model: str | None = None,
    host: str | None = None,
    port: int | None = None,
    device: str | None = None,
) -> int:
    """Stop the model server, then start it again.

    Parameters
    ----------
    model : str | None, optional
        Model name to run; defaults to the resolved config value.
    host : str | None, optional
        Host to bind; defaults to the resolved config value.
    port : int | None, optional
        Port to bind; defaults to the resolved config value.
    device : str | None, optional
        Device to run on; defaults to the resolved config value.

    Returns
    -------
    int
        The restarted model server's pid.
    """
    stop(host, port)
    return start(model, host, port, device)
