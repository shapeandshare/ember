"""Unit-level tests: no model load, no external processes except a spawned child
that is explicitly killed. Safe to run repeatedly and safe on a shared host.
"""

from __future__ import annotations

import inspect
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import ember.runtime as runtime
import pytest
from ember import models, opencode_config, paths, process

from tests.conftest import free_port


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
        if os.environ.get("EMBER_REQUIRE_MODEL") == "1":
            pytest.fail(f"model dir not present: {model_dir} (EMBER_REQUIRE_MODEL=1)")
        pytest.skip("model dir not present")
    module = runtime.joint_module(model_dir)
    for attr in ("systemone", "load_release_model", "encode_record", "collate_records"):
        assert hasattr(module, attr), f"joint_schema_model missing {attr}"


def test_model_max_length_reads_text_config(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"text_config": {"max_position_embeddings": 4096}})
    )
    assert runtime.model_max_length(model_dir) == 4096


def test_model_max_length_reads_top_level_config(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"max_position_embeddings": 8192})
    )
    assert runtime.model_max_length(model_dir) == 8192


def test_model_max_length_falls_back_without_a_config(tmp_path):
    assert runtime.model_max_length(tmp_path / "missing") == runtime.FALLBACK_MAX_LENGTH


def test_model_max_length_falls_back_when_zero(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"text_config": {"max_position_embeddings": 0}})
    )
    assert runtime.model_max_length(model_dir) == runtime.FALLBACK_MAX_LENGTH


def test_engine_max_length_defaults_to_the_model_maximum():
    default = (
        inspect.signature(runtime.Engine.__init__).parameters["max_length"].default
    )
    assert default is None


def test_engine_model_name_explicit_and_fallback(tmp_path, monkeypatch):
    model_dir = tmp_path / "my-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")

    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))

    engine_explicit = runtime.Engine(model_dir, model_name="full")
    assert engine_explicit.model_name == "full"
    assert engine_explicit.describe()["model"] == "full"

    engine_fallback = runtime.Engine(model_dir)
    assert engine_fallback.model_name == "my-model"
    assert engine_fallback.describe()["model"] == "my-model"

    engine_none = runtime.Engine(model_dir, model_name=None)
    assert engine_none.model_name == "my-model"

    engine_empty = runtime.Engine(model_dir, model_name="")
    assert engine_empty.model_name == ""


def test_pinned_model_declares_the_model_maximum():
    model_dir = runtime.DEFAULT_MODEL_DIR
    if not model_dir.is_dir():
        if os.environ.get("EMBER_REQUIRE_MODEL") == "1":
            pytest.fail(f"model dir not present: {model_dir} (EMBER_REQUIRE_MODEL=1)")
        pytest.skip("model dir not present")
    assert runtime.model_max_length(model_dir) == 262144


# --------------------------------------------------------------------------- #
# MCP server helpers (imported without loading the model)
# --------------------------------------------------------------------------- #
def test_mcp_server_import_does_not_load_torch():
    code = "import sys, ember.mcp_server; print('torch' in sys.modules)"
    result = subprocess.run(  # noqa: S603 - this interpreter with a literal script
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert result.stdout.strip() == "False", result.stderr


def test_mcp_server_ready_false_when_nothing_listening(monkeypatch):
    from ember import mcp_server

    monkeypatch.setattr(mcp_server, "SERVER_URL", f"http://127.0.0.1:{free_port()}")
    assert mcp_server._server_ready() is False


def test_ensure_server_raises_when_down_and_autostart_disabled(monkeypatch):
    from ember import mcp_server

    monkeypatch.setattr(mcp_server, "SERVER_URL", f"http://127.0.0.1:{free_port()}")
    monkeypatch.setattr(mcp_server, "AUTOSTART", False)
    with pytest.raises(RuntimeError, match="not reachable"):
        mcp_server._ensure_server()


# --------------------------------------------------------------------------- #
# process lifecycle (state isolated under a temporary EMBER_STATE_DIR)
# --------------------------------------------------------------------------- #
def test_spawn_records_pid_and_log_in_state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    proc = process.spawn(tmp_path / "no-model", "127.0.0.1", free_port(), "cpu")
    try:
        assert paths.pid_path() == tmp_path / "state" / "server.pid"
        assert int(paths.pid_path().read_text()) == proc.pid
        assert paths.server_log_path().exists()
    finally:
        proc.terminate()
        proc.wait(timeout=15)


def test_tracked_pid_ignores_a_pid_that_is_not_an_ember_server(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    paths.pid_path().write_text(str(os.getpid()))
    assert process.tracked_pid("127.0.0.1", free_port()) is None
    assert not paths.pid_path().exists()


def test_stop_without_a_tracked_server_signals_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    assert process.stop("127.0.0.1", free_port()) is False


def test_start_fails_fast_when_the_model_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("EMBER_MODEL_DIR", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="model pull"):
        process.start(host="127.0.0.1", port=free_port(), timeout=5)


# --------------------------------------------------------------------------- #
# models and opencode configuration
# --------------------------------------------------------------------------- #
def test_model_revisions_are_pinned_commits():
    for spec in models.REGISTRY.values():
        assert re.fullmatch(r"[0-9a-f]{40}", spec.revision), (
            f"{spec.name} is not pinned"
        )


def test_model_dir_override_applies_to_the_run_not_the_listing(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBER_MODEL_DIR", str(tmp_path))
    assert models.resolve_dir("full") == tmp_path
    assert models.resolve_dir("full", override=False) != tmp_path


def test_opencode_config_write_merges_and_is_idempotent(tmp_path):
    target = tmp_path / "opencode.json"
    target.write_text(
        json.dumps(
            {
                "model": "keep-me",
                "mcp": {"other": {"type": "remote", "url": "http://x"}},
            }
        )
    )

    opencode_config.write(target, "127.0.0.1", 9999, "1")
    first = target.read_text()
    config = json.loads(first)
    assert config["model"] == "keep-me"
    assert "other" in config["mcp"]
    entry = config["mcp"]["ember"]
    assert entry["type"] == "local"
    assert entry["enabled"] is True
    assert Path(entry["command"][0]).is_absolute()
    assert entry["environment"]["EMBER_SERVER_URL"] == "http://127.0.0.1:9999"

    opencode_config.write(target, "127.0.0.1", 9999, "1")
    assert target.read_text() == first


def test_opencode_config_remove_drops_only_our_entry(tmp_path):
    target = tmp_path / "opencode.json"
    opencode_config.write(target, "127.0.0.1", 9999, "1")
    config = json.loads(target.read_text())
    config["mcp"]["other"] = {"type": "remote", "url": "http://x"}
    target.write_text(json.dumps(config))

    assert opencode_config.remove(target) is True
    remaining_mcp = json.loads(target.read_text())["mcp"]
    assert "ember" not in remaining_mcp
    assert remaining_mcp["other"] == {"type": "remote", "url": "http://x"}
    assert opencode_config.remove(target) is False
