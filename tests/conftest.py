"""Shared fixtures for the ember test suite.

Isolation rules (important on a host with other opencode instances running):
  * Tests NEVER use the default port 8765; they bind a random free port.
  * Tests only start/stop processes they own (tracked by PID), never by port scan.
  * Tests never invoke the opencode CLI or touch global opencode config.
  * The model is loaded once per session (session-scoped server).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from evals import analysis, metrics

from tests.test_eval_benchmark import DATASET, ITEMS, _answers

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
    # import-placement:allow - deferred; mcp import triggers network probes at load
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
        args=["-m", "ember.mcp.mcp_server"],
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
        [sys.executable, "-m", "ember.serving.server"],
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


# ###########################################################################
# Benchmark report fixtures (shared by tests/test_eval_report*.py)
# ###########################################################################


@pytest.fixture(scope="module")
def synthetic_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write a results file and trace the way ``scripts/run_evals.py`` does."""
    directory = tmp_path_factory.mktemp("results")
    run_id = "clef-flash_20261003T000000Z"
    scored = []
    for index, item in enumerate(ITEMS):
        result = metrics.score_item(item, _answers(item, right=index % 3 != 0))
        result.update(
            latency_ms=900.0 + index, model="clef-flash", usage={}, answers={}
        )
        scored.append(result)
    trace = directory / f"{run_id}_trace.jsonl"
    trace.write_text("".join(json.dumps(r) + "\n" for r in scored), encoding="utf-8")
    config = {
        "run_id": run_id,
        "timestamp": "20261003T000000Z",
        "git_hash": "abc1234",
        "model": "clef-flash",
        "model_spec": {
            "name": "flash",
            "repo": "Cloudflare/clef-flash",
            "params": "9B",
            "revision": "17f0b0a",
        },
        "engine": {"device": "mps", "dtype": "float16", "max_length": 262144},
        "host": {
            "platform": "macOS-26.0-arm64",
            "cpu": "Apple M4 Max",
            "python": "3.12.11",
            "packages": {"torch": "2.14.1"},
        },
        "server": "http://127.0.0.1:8765",
        "dataset": DATASET.name,
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "trace": trace.name,
        "split": None,
        "category": None,
        "n_items": len(scored),
        "n_errors": 0,
        "latency_ms": {"mean": 957.5, "p50": 957.0, "p95": 1009.0, "max": 1015.0},
    }
    results = directory / f"{run_id}_results.json"
    results.write_text(
        json.dumps({"config": config, "summary": metrics.aggregate(scored)}),
        encoding="utf-8",
    )
    return results


@pytest.fixture(scope="module")
def report(synthetic_run: Path) -> dict:
    return analysis.build(synthetic_run, dataset_path=DATASET)


@pytest.fixture(scope="module")
def bundle(synthetic_run: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    # import-placement:allow - deferred; loaded only for model-backed tests
    from evals import export

    return export.export(synthetic_run, tmp_path_factory.mktemp("bundle"))
