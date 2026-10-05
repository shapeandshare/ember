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

import ember.serving.runtime as runtime
import pytest
from ember import models
from ember.cfg import paths
from ember.opencode import opencode_config
from ember.serving import process

from tests.conftest import free_port


# ###########################################################################
# runtime helpers
# ###########################################################################
def test_pick_device_defaults_to_available_accelerator():
    # import-placement:allow - deferred; torch must not load at module collect time
    import torch

    expected = "mps" if torch.backends.mps.is_available() else "cpu"
    assert runtime.pick_device() == expected


def test_pick_device_explicit_passthrough():
    assert runtime.pick_device("cpu") == "cpu"
    assert runtime.pick_device("mps") == "mps"


def test_pick_dtype_is_fp16_on_mps_fp32_on_cpu():
    # import-placement:allow - deferred; torch must not load at module collect time
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


# ###########################################################################
# S-001: loopback validation helper
# ###########################################################################
def test_validate_server_url_accepts_default_loopback():
    from ember.mcp import mcp_server

    # Must not raise for the default safe URL.
    mcp_server.validate_server_url("http://127.0.0.1:8765")


def test_validate_server_url_accepts_localhost():
    from ember.mcp import mcp_server

    mcp_server.validate_server_url("http://localhost:8765")


def test_validate_server_url_accepts_ipv6_loopback():
    from ember.mcp import mcp_server

    mcp_server.validate_server_url("http://[::1]:8765")


def test_validate_server_url_accepts_loopback_range():
    from ember.mcp import mcp_server

    # 127.x.x.x is the full loopback block.
    mcp_server.validate_server_url("http://127.0.0.2:8765")


def test_validate_server_url_rejects_remote_host():
    from ember.mcp import mcp_server

    with pytest.raises(ValueError, match="loopback"):
        mcp_server.validate_server_url("http://192.168.1.1:8765")


def test_validate_server_url_rejects_0_0_0_0():
    from ember.mcp import mcp_server

    with pytest.raises(ValueError, match="loopback"):
        mcp_server.validate_server_url("http://0.0.0.0:8765")


def test_validate_server_url_rejects_external_hostname():
    from ember.mcp import mcp_server

    with pytest.raises(ValueError, match="loopback"):
        mcp_server.validate_server_url("http://example.com:8765")


def test_validate_server_url_error_mentions_security_md():
    from ember.mcp import mcp_server

    with pytest.raises(ValueError, match=r"SECURITY\.md"):
        mcp_server.validate_server_url("http://10.0.0.1:8765")


# ###########################################################################
# S-001: CLI host normalisation
# ###########################################################################
def test_cmd_mcp_normalises_0_0_0_0_to_loopback(monkeypatch, tmp_path):
    """ember mcp --host 0.0.0.0 must set EMBER_SERVER_URL to 127.0.0.1, not 0.0.0.0."""
    import argparse

    from ember import cli

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "ember.mcp.mcp_server.main",
        lambda: captured.update({"url": os.environ.get("EMBER_SERVER_URL", "")}),
    )

    args = argparse.Namespace(host="0.0.0.0", port=free_port(), device=None, model=None)  # noqa: S104 - testing normalisation of this value, not binding
    cli.cmd_mcp(args)
    assert "0.0.0.0" not in captured["url"], (  # noqa: S104 - asserting the value is absent, not binding
        f"EMBER_SERVER_URL should not contain 0.0.0.0; got {captured['url']!r}"
    )
    assert "127.0.0.1" in captured["url"]


# ###########################################################################
# T-003: ALLOWED_MEDIA_KWARGS allowlist
# ###########################################################################
def test_allowed_media_kwargs_constant_exists():
    assert hasattr(runtime, "ALLOWED_MEDIA_KWARGS"), (
        "runtime must expose ALLOWED_MEDIA_KWARGS"
    )


def test_allowed_media_kwargs_is_frozenset():
    assert isinstance(runtime.ALLOWED_MEDIA_KWARGS, frozenset)


def test_allowed_media_kwargs_contains_expected_keys():
    expected = {
        "min_pixels",
        "max_pixels",
        "fps",
        "min_frames",
        "max_frames",
        "do_resize",
        "size",
        "do_convert_rgb",
    }
    assert expected == runtime.ALLOWED_MEDIA_KWARGS


def test_check_media_kwargs_passes_for_allowed_key(monkeypatch, tmp_path):
    """An allowed key must not raise."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir)
    # Patch joint_module to avoid actual model call.
    fake_response: dict = {
        "answers": {},
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }

    def fake_systemone(*a, **kw):
        return fake_response

    fake_module = type("M", (), {"systemone": staticmethod(fake_systemone)})()
    monkeypatch.setattr(runtime, "joint_module", lambda *a, **kw: fake_module)
    # Should not raise.
    engine.advise("state", {}, media_kwargs={"min_pixels": 256})


def test_check_media_kwargs_rejects_unknown_key(monkeypatch, tmp_path):
    """An unknown key must raise ValueError listing permitted keys."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir)
    fake_response: dict = {
        "answers": {},
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }

    def fake_systemone(*a, **kw):
        return fake_response

    fake_module = type("M", (), {"systemone": staticmethod(fake_systemone)})()
    monkeypatch.setattr(runtime, "joint_module", lambda *a, **kw: fake_module)
    with pytest.raises(ValueError, match="not permitted"):
        engine.advise("state", {}, media_kwargs={"unknown_key": "value"})


def test_check_media_kwargs_rejects_previously_reserved_key(monkeypatch, tmp_path):
    """Previously-reserved keys (text, images, videos, return_tensors) are not on the
    allowlist and must still be rejected."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir)
    fake_response: dict = {
        "answers": {},
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }

    def fake_systemone(*a, **kw):
        return fake_response

    fake_module = type("M", (), {"systemone": staticmethod(fake_systemone)})()
    monkeypatch.setattr(runtime, "joint_module", lambda *a, **kw: fake_module)
    for key in ("text", "images", "videos", "return_tensors"):
        with pytest.raises(ValueError, match="not permitted"):
            engine.advise("state", {}, media_kwargs={key: "x"})


# ###########################################################################
# MCP server helpers (imported without loading the model)
# ###########################################################################
def test_mcp_server_import_does_not_load_torch():
    code = "import sys, ember.mcp.mcp_server; print('torch' in sys.modules)"
    result = subprocess.run(  # noqa: S603 - this interpreter with a literal script
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert result.stdout.strip() == "False", result.stderr


def test_mcp_server_ready_false_when_nothing_listening(monkeypatch):
    # import-placement:allow - deferred; mcp_server imports torch at module load
    from ember.mcp import mcp_server

    monkeypatch.setattr(mcp_server, "SERVER_URL", f"http://127.0.0.1:{free_port()}")
    assert mcp_server._server_ready() is False


def test_ensure_server_raises_when_down_and_autostart_disabled(monkeypatch):
    # import-placement:allow - deferred; mcp_server imports torch at module load
    from ember.mcp import mcp_server

    monkeypatch.setattr(mcp_server, "SERVER_URL", f"http://127.0.0.1:{free_port()}")
    monkeypatch.setattr(mcp_server, "AUTOSTART", False)
    with pytest.raises(RuntimeError, match="not reachable"):
        mcp_server._ensure_server()


# ###########################################################################
# process lifecycle (state isolated under a temporary EMBER_STATE_DIR)
# ###########################################################################
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


# ###########################################################################
# models and opencode configuration
# ###########################################################################
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
