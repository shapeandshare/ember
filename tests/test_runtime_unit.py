"""Unit-level tests: no model load, no external processes except a spawned child
that is explicitly killed. Safe to run repeatedly and safe on a shared host.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, free_port, terminate_pid

import clef_local.runtime as runtime  # noqa: E402
from clef_local import models, opencode_config  # noqa: E402


# --------------------------------------------------------------------------- #
# runtime helpers
# --------------------------------------------------------------------------- #
def test_pick_device_defaults_to_available_accelerator():
    import torch

    expected = "mps" if torch.backends.mps.is_available() else "cpu"
    assert runtime.pick_device() == expected


def test_pick_device_explicit_passthrough():
    assert runtime.pick_device("cpu") == "cpu"
    assert runtime.pick_device("mps") == "mps"


def test_pick_dtype_is_fp16_on_mps_fp32_on_cpu():
    import torch

    assert runtime.pick_dtype("mps") == torch.float16
    assert runtime.pick_dtype("cpu") == torch.float32


def test_load_clef_missing_dir_raises():
    with pytest.raises(FileNotFoundError):
        runtime.load_clef("/nonexistent/clef-flash")


def test_joint_module_exposes_expected_api():
    model_dir = runtime.DEFAULT_MODEL_DIR
    if not model_dir.is_dir():
        if os.environ.get("CLEF_REQUIRE_MODEL") == "1":
            pytest.fail(f"model dir not present: {model_dir} (CLEF_REQUIRE_MODEL=1)")
        pytest.skip("model dir not present")
    module = runtime.joint_module(model_dir)
    for attr in ("systemone", "load_release_model", "encode_record", "collate_records"):
        assert hasattr(module, attr), f"joint_schema_model missing {attr}"


# --------------------------------------------------------------------------- #
# MCP server helpers (imported without loading the model)
# --------------------------------------------------------------------------- #
def test_mcp_server_ready_false_when_nothing_listening(monkeypatch):
    from clef_local import mcp_server

    monkeypatch.setattr(mcp_server, "SERVER_URL", f"http://127.0.0.1:{free_port()}")
    assert mcp_server._server_ready() is False


def test_ensure_server_raises_when_down_and_autostart_disabled(monkeypatch):
    from clef_local import mcp_server

    monkeypatch.setattr(mcp_server, "SERVER_URL", f"http://127.0.0.1:{free_port()}")
    monkeypatch.setattr(mcp_server, "AUTOSTART", False)
    with pytest.raises(RuntimeError, match="not reachable"):
        mcp_server._ensure_server()


def test_start_server_honors_configured_port_and_records_pid(tmp_path, monkeypatch):
    """Autostart must launch the child on the port in SERVER_URL and record its PID
    so it can be stopped without touching unrelated processes."""
    from clef_local import mcp_server

    port = free_port()
    pidfile = tmp_path / "server.pid"
    monkeypatch.setattr(mcp_server, "SERVER_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("CLEF_AUTOSTART_PIDFILE", str(pidfile))
    monkeypatch.setenv("CLEF_SERVER_LOG", str(tmp_path / "server.log"))
    # CPU keeps this lightweight; we kill it before inference anyway.
    monkeypatch.setenv("CLEF_DEVICE", "cpu")

    pid = mcp_server._start_server()
    try:
        assert isinstance(pid, int) and pid > 0
        deadline = time.time() + 10
        while time.time() < deadline and not pidfile.exists():
            time.sleep(0.1)
        assert pidfile.exists(), "autostart did not record a pidfile"
        assert int(pidfile.read_text().strip()) == pid
        os.kill(pid, 0)  # raises if not alive
    finally:
        terminate_pid(pid)


# --------------------------------------------------------------------------- #
# project configuration (no opencode CLI involved)
# --------------------------------------------------------------------------- #
def test_model_revisions_are_pinned_commits():
    for spec in models.REGISTRY.values():
        assert re.fullmatch(r"[0-9a-f]{40}", spec.revision), f"{spec.name} is not pinned"


def test_opencode_config_write_merges_and_is_idempotent(tmp_path):
    target = tmp_path / "opencode.json"
    target.write_text(
        json.dumps({"model": "keep-me", "mcp": {"other": {"type": "remote", "url": "http://x"}}})
    )

    opencode_config.write(target, "127.0.0.1", 9999, "1")
    first = target.read_text()
    config = json.loads(first)
    assert config["model"] == "keep-me"
    assert "other" in config["mcp"]
    entry = config["mcp"]["clef"]
    assert entry["type"] == "local" and entry["enabled"] is True
    assert Path(entry["command"][0]).is_absolute()
    assert entry["environment"]["CLEF_SERVER_URL"] == "http://127.0.0.1:9999"

    opencode_config.write(target, "127.0.0.1", 9999, "1")
    assert target.read_text() == first


def test_management_script_status_is_inert_on_unused_port():
    """`status` on a free port must report not running and never start/kill anything."""
    script = REPO_ROOT / "scripts" / "clef-server.sh"
    if not script.exists():
        pytest.skip("management script missing")
    port = free_port()
    env = dict(os.environ, CLEF_PORT=str(port))
    out = subprocess.run(
        [str(script), "status"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert out.returncode == 0
    assert "not running" in out.stdout.lower()
