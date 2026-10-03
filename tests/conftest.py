"""Shared fixtures for the ember test suite.

Isolation rules (important on a host with other opencode instances running):
  * Tests NEVER use the default port 8765; they bind a random free port.
  * Tests only start/stop processes they own (tracked by PID), never by port scan.
  * Tests never invoke the opencode CLI or touch global opencode config.
  * The model is loaded once per session (session-scoped server).
"""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / ".models" / "clef-flash"
SERVER_TIMEOUT = float(os.environ.get("EMBER_TEST_START_TIMEOUT", "300"))
# Ports the test suite must never touch (the user's warm servers).
PROTECTED_PORTS = {8765}


def free_port() -> int:
    """Ask the OS for an unused ephemeral port on loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    if port in PROTECTED_PORTS:
        return free_port()
    return port


def terminate_pid(pid: int, timeout: float = 10.0) -> None:
    """Terminate one process by PID (SIGTERM, then SIGKILL); never scans ports."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def mcp_stdin_params(base_url: str, *, autostart: str = "0", **extra_env: str):
    """Build StdioServerParameters for the MCP server, pointed at a test server."""
    from mcp.client.stdio import StdioServerParameters

    env = dict(os.environ)
    env.update(
        {
            "EMBER_SERVER_URL": base_url,
            "EMBER_AUTOSTART": autostart,
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
        }
    )
    env.update({k: str(v) for k, v in extra_env.items()})
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "ember.mcp_server"],
        cwd=str(REPO_ROOT),
        env=env,
    )


def _server_log_tail(log_path: Path, limit: int = 4000) -> str:
    """The tail of a spawned server's log, for actionable CI failures."""
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return ""


@pytest.fixture(scope="session")
def base_url(tmp_path_factory) -> str:
    """Start one isolated ember server on a random port for the whole session."""
    if not MODEL_DIR.is_dir():
        message = f"Clef-Flash weights not found at {MODEL_DIR} (run: make download)"
        if os.environ.get("EMBER_REQUIRE_MODEL") == "1":
            pytest.fail(
                f"{message} (EMBER_REQUIRE_MODEL=1: failing instead of skipping)"
            )
        pytest.skip(message)

    port = free_port()
    env = dict(os.environ)
    env.update(
        {
            "EMBER_HOST": "127.0.0.1",
            "EMBER_PORT": str(port),
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
        }
    )
    log_path = tmp_path_factory.mktemp("ember-server") / "server.log"
    handle = open(log_path, "ab")
    proc = subprocess.Popen(
        [sys.executable, "-m", "ember.server"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=handle,
        stderr=handle,
        stdin=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + SERVER_TIMEOUT
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"test server exited early rc={proc.returncode}; see {log_path}\n"
                    f"--- server.log tail ---\n{_server_log_tail(log_path)}"
                )
            with contextlib.suppress(httpx.HTTPError):
                resp = httpx.get(f"{url}/health", timeout=2.0)
                if resp.status_code == 200 and resp.json().get("engine"):
                    break
            time.sleep(1.0)
        else:
            raise RuntimeError(
                f"test server not ready within {SERVER_TIMEOUT}s; see {log_path}\n"
                f"--- server.log tail ---\n{_server_log_tail(log_path)}"
            )
        yield url
    finally:
        handle.close()
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
