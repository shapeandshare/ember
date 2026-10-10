"""Unit-level tests: no model load, no external processes except a spawned child
that is explicitly killed. Safe to run repeatedly and safe on a shared host.
"""

from __future__ import annotations

import base64
import inspect
import io
import json
import logging
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import ember.serving.runtime as runtime
import pytest
from ember import models
from ember.cfg import paths
from ember.opencode import opencode_config
from ember.serving import devices, limits, media, process
from ember.serving.limit_source import LimitSource
from ember.serving.limits import Limits
from ember.serving.request_size import RequestSize, refusal_message
from PIL import Image

from tests.conftest import free_port
from tests.fake_joint import FakeJointModule, record_length


def _limits(max_request_length: int = 0, max_length: int = 262144) -> Limits:
    return Limits(
        max_length=max_length,
        max_length_source=LimitSource.MODEL,
        max_request_length=max_request_length,
        max_request_length_source=LimitSource.OPERATOR,
    )


# ###########################################################################
# runtime helpers
# ###########################################################################
def test_pick_device_defaults_to_available_accelerator():
    # import-placement:allow - deferred; torch must not load at module collect time
    import torch

    if torch.backends.mps.is_available():
        expected = "mps"
    elif torch.cuda.is_available():
        expected = "cuda"
    else:
        expected = "cpu"
    assert devices.pick_device() == expected


def test_default_model_dir_matches_checkout_model_dir():
    """runtime and the model registry must agree on the checkout's .models dir."""
    assert models._dev_dir(models.get("flash")) == runtime.DEFAULT_MODEL_DIR


def test_pick_device_explicit_passthrough():
    assert devices.pick_device("cpu") == "cpu"
    assert devices.pick_device("mps") == "mps"
    assert devices.pick_device("cuda") == "cuda"


def test_pick_device_prefers_mps_over_cuda_when_both_available(monkeypatch):
    """Constitution Article VI ("Apple Silicon and CUDA"): MPS is the
    local-first default; a host with both backends available (unusual, but
    not impossible in a mocked test) still prefers MPS."""
    monkeypatch.setattr(devices.torch.backends.mps, "is_available", lambda: True)
    monkeypatch.setattr(devices.torch.cuda, "is_available", lambda: True)
    assert devices.pick_device("auto") == "mps"


def test_pick_device_falls_back_to_cuda_when_mps_unavailable(monkeypatch):
    """The hosted-deployment case (e.g. Outerbounds): Linux compute has no
    MPS, so an available CUDA GPU must be selected instead of falling
    straight through to CPU."""
    monkeypatch.setattr(devices.torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr(devices.torch.cuda, "is_available", lambda: True)
    assert devices.pick_device("auto") == "cuda"


def test_pick_device_falls_back_to_cpu_when_neither_accelerator_available(
    monkeypatch,
):
    monkeypatch.setattr(devices.torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr(devices.torch.cuda, "is_available", lambda: False)
    assert devices.pick_device("auto") == "cpu"


def test_pick_dtype_is_fp16_on_mps_fp32_on_cpu():
    # import-placement:allow - deferred; torch must not load at module collect time
    import torch

    assert devices.pick_dtype("mps") == torch.float16
    assert devices.pick_dtype("cpu") == torch.float32


def test_pick_dtype_is_fp16_on_cuda():
    """Constitution Article VI: CUDA uses float16 by default, matching MPS —
    not float32 (the CPU-only rule)."""
    # import-placement:allow - deferred; torch must not load at module collect time
    import torch

    assert devices.pick_dtype("cuda") == torch.float16


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


@pytest.mark.model
def test_engine_loads_through_unmodified_loader():
    """Engine/load_clef load the default model dir with no registry-specific
    branching — skipped when weights are not pulled locally."""
    model_dir = runtime.DEFAULT_MODEL_DIR
    if not model_dir.is_dir():
        if os.environ.get("EMBER_REQUIRE_MODEL") == "1":
            pytest.fail(f"model dir not present: {model_dir} (EMBER_REQUIRE_MODEL=1)")
        pytest.skip("model dir not present")
    engine = runtime.Engine(model_dir)
    assert engine.model_dir == model_dir


def test_engine_max_length_defaults_to_the_model_maximum(tmp_path, monkeypatch):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"text_config": {"max_position_embeddings": 4096}})
    )
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    default = inspect.signature(runtime.Engine.__init__).parameters["limits"].default
    assert default is None
    engine = runtime.Engine(model_dir)
    assert engine.max_length == 4096
    assert engine.limits.max_length_source is LimitSource.MODEL


def test_engine_max_length_follows_its_limits(tmp_path, monkeypatch):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits(max_length=8192))
    assert engine.max_length == 8192


def test_engine_model_name_explicit_and_fallback(tmp_path, monkeypatch):
    model_dir = tmp_path / "my-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")

    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))

    engine_explicit = runtime.Engine(model_dir, model_name="full", limits=_limits())
    assert engine_explicit.model_name == "full"
    assert engine_explicit.describe()["model"] == "full"

    engine_fallback = runtime.Engine(model_dir, limits=_limits())
    assert engine_fallback.model_name == "my-model"
    assert engine_fallback.describe()["model"] == "my-model"

    engine_none = runtime.Engine(model_dir, model_name=None, limits=_limits())
    assert engine_none.model_name == "my-model"

    engine_empty = runtime.Engine(model_dir, model_name="", limits=_limits())
    assert engine_empty.model_name == ""


# ###########################################################################
# I-001: Engine.describe() must not leak model_dir (filesystem path)
# ###########################################################################
def test_engine_describe_omits_model_dir(tmp_path, monkeypatch):
    """I-001: Engine.describe() must not include model_dir — /health forwards
    this to any loopback caller, disclosing the full filesystem path."""
    model_dir = tmp_path / "my-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())
    description = engine.describe()
    assert "model_dir" not in description, (
        "Engine.describe() must not expose model_dir (I-001: path disclosure)"
    )


def test_engine_describe_still_has_required_fields(tmp_path, monkeypatch):
    """I-001: removing model_dir must not drop the fields callers depend on."""
    model_dir = tmp_path / "my-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())
    description = engine.describe()
    for field in ("model", "device", "dtype", "max_length"):
        assert field in description, (
            f"Engine.describe() missing required field: {field}"
        )


def test_engine_describe_reports_its_limits_and_their_sources(tmp_path, monkeypatch):
    model_dir = tmp_path / "my-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(
        model_dir,
        limits=Limits(
            max_length=65536,
            max_length_source=LimitSource.OPERATOR,
            max_request_length=8192,
            max_request_length_source=LimitSource.MEASURED,
        ),
    )
    description = engine.describe()
    assert set(description) == {
        "model",
        "device",
        "dtype",
        "max_length",
        "max_length_source",
        "max_request_length",
        "max_request_length_source",
    }
    assert description["max_length"] == 65536
    assert description["max_request_length"] == 8192
    assert description["max_length_source"] == "operator"
    assert description["max_request_length_source"] == "measured"
    assert type(description["max_length_source"]) is str
    assert type(description["max_request_length_source"]) is str


def test_pinned_model_declares_the_model_maximum():
    model_dir = runtime.DEFAULT_MODEL_DIR
    if not model_dir.is_dir():
        if os.environ.get("EMBER_REQUIRE_MODEL") == "1":
            pytest.fail(f"model dir not present: {model_dir} (EMBER_REQUIRE_MODEL=1)")
        pytest.skip("model dir not present")
    assert limits.model_max_length(model_dir) == 262144


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
# ###########################################################################
# I-003: model dir must be removed from sys.path after joint_schema_model import
# ###########################################################################
def test_joint_module_removes_model_dir_from_sys_path_after_import(
    tmp_path, monkeypatch
):
    """I-003: joint_module() must remove the model directory from sys.path
    after importing joint_schema_model so tracebacks do not leak the path."""
    import builtins
    import sys

    model_dir = tmp_path / "my-model"
    model_dir.mkdir()
    fake_module = type("FakeJSM", (), {})()

    monkeypatch.setattr(runtime, "_JOINT_MODULE", None)
    sys.modules.pop("joint_schema_model", None)

    real_import = builtins.__import__

    def patched_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "joint_schema_model":
            sys.modules["joint_schema_model"] = fake_module  # type: ignore[assignment]
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", patched_import)

    model_path = str(model_dir.resolve())
    while model_path in sys.path:
        sys.path.remove(model_path)

    runtime.joint_module(model_dir)

    assert model_path not in sys.path, (
        "I-003: joint_module() must remove model_dir from sys.path after import"
    )
    sys.modules.pop("joint_schema_model", None)
    monkeypatch.setattr(runtime, "_JOINT_MODULE", None)


def test_allowed_media_kwargs_constant_exists():
    assert hasattr(media, "ALLOWED_MEDIA_KWARGS"), (
        "media must expose ALLOWED_MEDIA_KWARGS"
    )


def test_allowed_media_kwargs_is_frozenset():
    assert isinstance(media.ALLOWED_MEDIA_KWARGS, frozenset)


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
        "cap_pixels_per_frame",
    }
    assert expected == media.ALLOWED_MEDIA_KWARGS


def test_check_media_kwargs_passes_for_allowed_key(monkeypatch, tmp_path):
    """An allowed key must not raise."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())
    # Patch joint_module to avoid actual model call.
    fake_module = FakeJointModule()
    monkeypatch.setattr(runtime, "joint_module", lambda *a, **kw: fake_module)
    # Should not raise.
    engine.advise("state", {}, media_kwargs={"min_pixels": 256})


def test_check_media_kwargs_rejects_unknown_key(monkeypatch, tmp_path):
    """An unknown key must raise ValueError listing permitted keys."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())
    fake_module = FakeJointModule()
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
    engine = runtime.Engine(model_dir, limits=_limits())
    fake_module = FakeJointModule()
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


def test_cli_import_does_not_load_torch():
    # The cli.py split must not pull torch in at parser-build time.
    code = "import sys, ember.cli; print('torch' in sys.modules)"
    result = subprocess.run(  # noqa: S603 - this interpreter with a literal script
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert result.stdout.strip() == "False", result.stderr


# ###########################################################################
# TORCH_DISABLE_NATIVE_JIT: torch 2.14's torch._native registers Triton-backed
# ops (e.g. aten::bmm's outer-product specialization, hit by Qwen3.5's RoPE
# forward on CUDA) that JIT-compile a kernel via Triton at first use — this
# requires a C compiler, which a minimal CUDA container (e.g. Outerbounds'
# Fast Bakery base image) does not have, and there is no way to install one
# through that deployment's contract. Unlike PYTORCH_ENABLE_MPS_FALLBACK
# (Apple Silicon), this failure is a hard RuntimeError with no automatic
# fallback — see
# vault/decisions/2026-10-10-disable-torch-native-jit-for-cuda-compiler-gap.md.
# ###########################################################################
_PRINT_TORCH_DISABLE_NATIVE_JIT = (
    "import os, ember.serving.runtime; "
    "print(os.environ.get('TORCH_DISABLE_NATIVE_JIT'))"
)


def test_runtime_import_sets_torch_disable_native_jit_before_torch_loads():
    """runtime.py must set TORCH_DISABLE_NATIVE_JIT (torch's own kill switch
    for all _native DSL-backed op registrations — Triton, CuteDSL, Helion)
    before `import torch`, exactly like PYTORCH_ENABLE_MPS_FALLBACK. A
    subprocess is required: torch is already imported in this test process,
    so the module-level os.environ.setdefault has already run and checking
    os.environ here would not prove the ordering. TORCH_DISABLE_NATIVE_JIT
    is explicitly cleared from the subprocess's env: this test file's own
    module-level `import ember.serving.runtime as runtime` already set it in
    this pytest process, and subprocess.run inherits the parent's os.environ
    by default — without clearing it, the child would start with the value
    already set, defeating what this test is trying to prove."""
    env = {k: v for k, v in os.environ.items() if k != "TORCH_DISABLE_NATIVE_JIT"}
    result = subprocess.run(  # noqa: S603 - this interpreter with a literal script
        [sys.executable, "-c", _PRINT_TORCH_DISABLE_NATIVE_JIT],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.stdout.strip() == "1", result.stderr


def test_ember_torch_disable_native_jit_env_var_overrides_the_default():
    """An operator with a working CUDA compiler toolchain (so the Triton path
    actually works and may be faster) can opt back in by setting
    EMBER_TORCH_DISABLE_NATIVE_JIT=0 — runtime.py must respect it rather than
    always forcing TORCH_DISABLE_NATIVE_JIT=1. TORCH_DISABLE_NATIVE_JIT is
    explicitly cleared from the subprocess's env for the same reason as
    above (this test file's own module-level runtime import already set it
    in this pytest process)."""
    env = {k: v for k, v in os.environ.items() if k != "TORCH_DISABLE_NATIVE_JIT"}
    env["EMBER_TORCH_DISABLE_NATIVE_JIT"] = "0"
    result = subprocess.run(  # noqa: S603 - this interpreter with a literal script
        [sys.executable, "-c", _PRINT_TORCH_DISABLE_NATIVE_JIT],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.stdout.strip() == "0", result.stderr


def _endpoint(url: str, *, is_local: bool):
    from urllib.parse import urlparse

    from ember.cfg.endpoint import Endpoint

    parsed = urlparse(url)
    return Endpoint(
        url=url,
        host=parsed.hostname or "127.0.0.1",
        scheme=parsed.scheme,
        is_local=is_local,
        allow_insecure_transport=False,
        request_timeout=1,
    )


def test_ensure_server_is_a_noop_for_a_remote_endpoint(monkeypatch):
    from ember.mcp import mcp_server

    monkeypatch.setattr(mcp_server, "AUTOSTART", False)
    remote = _endpoint("https://example.invalid", is_local=False)
    mcp_server._ensure_server(remote)


def test_ensure_server_raises_when_down_and_autostart_disabled(monkeypatch):
    from ember.mcp import mcp_server

    local = _endpoint(f"http://127.0.0.1:{free_port()}", is_local=True)
    monkeypatch.setattr(mcp_server, "AUTOSTART", False)
    with pytest.raises(RuntimeError, match="not reachable"):
        mcp_server._ensure_server(local)


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


# ###########################################################################
# stop() audit logging (R-001)
# ###########################################################################
def test_stop_writes_sigterm_audit_entry_to_server_log(tmp_path, monkeypatch):
    """stop() appends a timestamped SIGTERM audit entry to server.log."""
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    fake_pid = 99999

    # Fake a tracked server: pid file exists, pid is "alive", is an ember server.
    # _pid_alive must return True so tracked_pid accepts the pid, then False so
    # the SIGTERM wait loop exits without spinning.
    alive_calls = {"count": 0}

    def fake_pid_alive(pid: int) -> bool:
        alive_calls["count"] += 1
        return alive_calls["count"] <= 1

    paths.pid_path().write_text(str(fake_pid))
    monkeypatch.setattr(process, "_pid_alive", fake_pid_alive)
    monkeypatch.setattr(process, "_is_ember_server", lambda pid: True)
    monkeypatch.setattr(process, "health", lambda *a, **kw: None)

    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    monkeypatch.setattr(process.os, "kill", fake_kill)

    result = process.stop("127.0.0.1", free_port())

    assert result is True
    log_text = paths.server_log_path().read_text(encoding="utf-8")
    assert f"stop: signaling pid={fake_pid}" in log_text
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", log_text)


def test_audit_log_failure_logs_warning_instead_of_printing(
    tmp_path, monkeypatch, caplog, capsys
):
    """A failed audit-log write is reported through logging, not print (§10.13)."""
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "missing" / "dir"))
    monkeypatch.setattr(
        process.paths, "server_log_path", lambda: tmp_path / "nope" / "server.log"
    )

    with caplog.at_level("WARNING", logger=process.__name__):
        process._append_audit_log("stop: signaling pid=1")

    assert "could not write audit log" in caplog.text
    assert capsys.readouterr().err == ""


def test_stop_writes_sigkill_audit_entry_when_escalating(tmp_path, monkeypatch):
    """stop() appends a SIGKILL escalation entry when the process survives SIGTERM."""
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    fake_pid = 99998

    paths.pid_path().write_text(str(fake_pid))
    # _pid_alive stays True (stubborn process) until SIGKILL is sent.
    # timeout=0.0 makes the wait loop exit immediately so SIGKILL is triggered.
    alive_state = {"alive": True}

    def fake_pid_alive(pid: int) -> bool:
        return alive_state["alive"]

    monkeypatch.setattr(process, "_pid_alive", fake_pid_alive)
    monkeypatch.setattr(process, "_is_ember_server", lambda pid: True)
    monkeypatch.setattr(process, "health", lambda *a, **kw: None)

    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))
        if sig == signal.SIGKILL:
            alive_state["alive"] = False

    monkeypatch.setattr(process.os, "kill", fake_kill)
    result = process.stop("127.0.0.1", free_port(), timeout=0.0)

    assert result is True
    sigs = [s for _, s in kill_calls]
    assert signal.SIGTERM in sigs
    assert signal.SIGKILL in sigs

    log_text = paths.server_log_path().read_text(encoding="utf-8")
    assert f"stop: signaling pid={fake_pid}" in log_text
    assert f"stop: escalating to SIGKILL for pid={fake_pid}" in log_text


def test_stop_writes_no_audit_entry_when_nothing_tracked(tmp_path, monkeypatch):
    """stop() writes nothing to server.log when no server is tracked."""
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    # No pid file → tracked_pid returns None → early return False.
    result = process.stop("127.0.0.1", free_port())

    assert result is False
    # Log file should not exist (or be empty) — no audit entry written.
    log_path = paths.server_log_path()
    if log_path.exists():
        assert log_path.read_text(encoding="utf-8") == ""


def test_stop_succeeds_even_when_log_write_raises_oserror(tmp_path, monkeypatch):
    """stop() still signals the pid and returns True when the log append fails."""
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    fake_pid = 99997

    paths.pid_path().write_text(str(fake_pid))
    alive_calls_oserr = {"count": 0}

    def fake_pid_alive_oserr(pid: int) -> bool:
        alive_calls_oserr["count"] += 1
        return alive_calls_oserr["count"] <= 1

    monkeypatch.setattr(process, "_pid_alive", fake_pid_alive_oserr)
    monkeypatch.setattr(process, "_is_ember_server", lambda pid: True)
    monkeypatch.setattr(process, "health", lambda *a, **kw: None)

    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    monkeypatch.setattr(process.os, "kill", fake_kill)

    # Make the log directory read-only so open() raises OSError.
    log_path = paths.server_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.chmod(0o555)

    try:
        result = process.stop("127.0.0.1", free_port())
    finally:
        log_path.parent.chmod(0o755)

    assert result is True
    sigs = [s for _, s in kill_calls]
    assert signal.SIGTERM in sigs


# ###########################################################################
# D-005: _spawn_locked() must serialise spawn vs already-up paths
# ###########################################################################
def test_spawn_locked_skips_spawn_when_server_already_up(tmp_path, monkeypatch):
    """D-005: _spawn_locked() must return None (no spawn) when is_up() is True
    inside the lock — the second concurrent caller path."""
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))

    spawn_calls: list[int] = []

    def fake_spawn(
        model_dir: object, host: object, p: object, device: object
    ) -> object:
        spawn_calls.append(1)

        class _FakeProc:
            pid = 42

        return _FakeProc()

    monkeypatch.setattr(process, "spawn", fake_spawn)
    monkeypatch.setattr(process, "is_up", lambda h, p: True)

    result = process._spawn_locked(tmp_path / "model", "127.0.0.1", free_port(), "cpu")

    assert result is None, "_spawn_locked() must return None when is_up() is True"
    assert len(spawn_calls) == 0, "D-005: spawn must not be called when server is up"


def test_spawn_locked_calls_spawn_when_server_is_down(tmp_path, monkeypatch):
    """D-005: _spawn_locked() must call spawn() and return the process when
    is_up() is False inside the lock — the first-caller path."""
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))

    class _FakeProc:
        pid = 99

    monkeypatch.setattr(process, "spawn", lambda *a, **kw: _FakeProc())
    monkeypatch.setattr(process, "is_up", lambda h, p: False)

    fake_dir = tmp_path / "model"
    fake_dir.mkdir()
    result = process._spawn_locked(fake_dir, "127.0.0.1", free_port(), "cpu")

    assert result is not None, "_spawn_locked() must return process when down"
    assert result.pid == 99


# ###########################################################################
# D-004: spawn() must create server.log for subprocess output
# ###########################################################################
def test_spawn_creates_server_log_file(tmp_path, monkeypatch):
    """D-004: spawn() must create server.log so subprocess output is captured.
    Log file rotation for the subprocess must be handled by an external
    logrotate configuration (RotatingFileHandler only rotates via emit(),
    which the child process never calls through the parent handler)."""
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    proc = process.spawn(tmp_path / "no-model", "127.0.0.1", free_port(), "cpu")
    try:
        assert paths.server_log_path().exists(), "D-004: spawn() must create server.log"
    finally:
        proc.terminate()
        proc.wait(timeout=15)


def test_start_fails_fast_when_the_model_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("EMBER_MODEL_DIR", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="model pull"):
        process.start(host="127.0.0.1", port=free_port(), timeout=5)


def test_start_fails_fast_in_the_parent_process_when_hosted_uri_is_malformed(
    tmp_path, monkeypatch
):
    """process.start() MUST check ember.serving.hosted.resolve() before
    spawning the server subprocess, so a malformed EMBER_MODEL_S3_URI fails
    fast in the parent `ember start` invocation rather than spawning a child
    that crashes during its own startup."""
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("EMBER_MODEL_S3_URI", "not-a-valid-uri")
    with pytest.raises(RuntimeError, match="EMBER_MODEL_S3_URI"):
        process.start(host="127.0.0.1", port=free_port(), timeout=5)


def test_start_uses_hosted_model_dir_when_configured(tmp_path, monkeypatch):
    """When the hosted path resolves successfully, process.start() must use
    its model_dir to spawn the server, never falling through to the
    REGISTRY-based model-pulled check (which would otherwise require a
    REGISTRY entry — the hosted path has none)."""
    from ember.serving import hosted

    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path))
    fake_dir = tmp_path / "hosted-model"
    fake_dir.mkdir()
    fake_source = hosted.HostedModelSource(
        uri="s3://my-bucket/clef-flash", model_dir=fake_dir
    )
    monkeypatch.setattr(hosted, "resolve", lambda: fake_source)

    captured: dict[str, object] = {}

    def _fake_spawn(model_dir, host, port, device):
        captured["model_dir"] = model_dir
        raise RuntimeError("stop before actually spawning a subprocess")

    monkeypatch.setattr(process, "spawn", _fake_spawn)

    with pytest.raises(RuntimeError, match="stop before actually spawning"):
        process.start(host="127.0.0.1", port=free_port(), timeout=5)

    assert captured["model_dir"] == fake_dir


# ###########################################################################
# models and opencode configuration
# ###########################################################################
def test_model_revisions_are_full_commit_shas_when_set():
    """revision is optional (constitution Article V, "Model Loading" — ember
    supports any model that can run, not a hand-maintained allowlist of
    pinned, hash-verified weights); when a REGISTRY entry does set one (as
    every current entry does, for download targeting), it must be a full
    commit SHA, not a branch name or partial hash."""
    for spec in models.REGISTRY.values():
        if spec.revision is not None:
            assert re.fullmatch(r"[0-9a-f]{40}", spec.revision), (
                f"{spec.name}'s revision is set but not a full commit SHA"
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


# ###########################################################################
# D-001: bounded admission control (semaphore)
# ###########################################################################
def test_max_pending_advise_constant_exists():
    """D-001: runtime must expose MAX_PENDING_ADVISE."""
    assert hasattr(runtime, "MAX_PENDING_ADVISE"), (
        "runtime must expose MAX_PENDING_ADVISE"
    )


def test_max_pending_advise_is_positive_int():
    """D-001: MAX_PENDING_ADVISE must be a positive integer."""
    assert isinstance(runtime.MAX_PENDING_ADVISE, int)
    assert runtime.MAX_PENDING_ADVISE > 0


def test_engine_has_admission_semaphore(monkeypatch, tmp_path):
    """D-001: Engine must carry a threading.Semaphore for admission control."""
    import threading

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())
    assert hasattr(engine, "_admission"), "Engine must have _admission attribute"
    assert isinstance(engine._admission, type(threading.Semaphore())), (
        "_admission must be a threading.Semaphore"
    )


def test_admission_semaphore_capacity_matches_constant(monkeypatch, tmp_path):
    """D-001: _admission semaphore capacity must equal MAX_PENDING_ADVISE."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())
    # Drain the semaphore to verify its initial count.
    acquired = 0
    while engine._admission.acquire(blocking=False):
        acquired += 1
    assert acquired == runtime.MAX_PENDING_ADVISE, (
        f"semaphore capacity {acquired} != "
        f"MAX_PENDING_ADVISE {runtime.MAX_PENDING_ADVISE}"
    )
    # Release all acquired slots to leave the engine in a clean state.
    for _ in range(acquired):
        engine._admission.release()


def test_advise_raises_when_admission_full(monkeypatch, tmp_path):
    """D-001: advise must raise RuntimeError when the admission semaphore is full."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())
    # Drain all admission slots.
    for _ in range(runtime.MAX_PENDING_ADVISE):
        engine._admission.acquire(blocking=False)
    fake_module = FakeJointModule()
    monkeypatch.setattr(runtime, "joint_module", lambda *a, **kw: fake_module)
    with pytest.raises(runtime.AdmissionError, match="server busy"):
        engine.advise("state", {})
    # Restore semaphore.
    for _ in range(runtime.MAX_PENDING_ADVISE):
        engine._admission.release()


def test_advise_succeeds_when_admission_has_capacity(monkeypatch, tmp_path):
    """D-001: advise must succeed when the admission semaphore has capacity."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())
    fake_response: dict = {
        "answers": {},
        "usage": {
            "input_tokens": record_length({"state": "state", "questions": {}}),
            "output_tokens": 0,
        },
    }
    fake_module = FakeJointModule(systemone=lambda *a, **kw: fake_response)
    monkeypatch.setattr(runtime, "joint_module", lambda *a, **kw: fake_module)
    # Must not raise.
    result = engine.advise("state", {})
    assert result == fake_response


def test_admission_slot_released_after_successful_advise(monkeypatch, tmp_path):
    """D-001: the admission slot must be released after a successful advise call."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())
    fake_module = FakeJointModule()
    monkeypatch.setattr(runtime, "joint_module", lambda *a, **kw: fake_module)
    engine.advise("state", {})
    # After the call, all slots must be available again.
    acquired = 0
    while engine._admission.acquire(blocking=False):
        acquired += 1
    assert acquired == runtime.MAX_PENDING_ADVISE
    for _ in range(acquired):
        engine._admission.release()


def test_admission_slot_released_after_failed_advise(monkeypatch, tmp_path):
    """D-001: the admission slot must be released even when advise raises."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir, limits=_limits())

    def boom(*a: object, **kw: object) -> dict:
        raise ValueError("simulated engine failure")

    fake_module = FakeJointModule(systemone=boom)
    monkeypatch.setattr(runtime, "joint_module", lambda *a, **kw: fake_module)
    with pytest.raises(ValueError, match="simulated"):
        engine.advise("state", {})
    # Slot must be restored.
    acquired = 0
    while engine._admission.acquire(blocking=False):
        acquired += 1
    assert acquired == runtime.MAX_PENDING_ADVISE
    for _ in range(acquired):
        engine._admission.release()


# ###########################################################################
# D-002: per-request token cap
# ###########################################################################
def test_max_request_length_default_in_config():
    """D-002: config DEFAULTS must include max_request_length, unset (None) so the
    loaded model's measured default applies."""
    from ember.cfg import config as cfg

    assert "max_request_length" in cfg.DEFAULTS, (
        "DEFAULTS must include max_request_length"
    )
    assert cfg.DEFAULTS["max_request_length"] is None, (
        "default max_request_length must be unset (None)"
    )


def _isolate_limit_config(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.delenv("EMBER_MAX_LENGTH", raising=False)
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    return model_dir


def test_max_request_length_env_override(monkeypatch, tmp_path):
    """D-002: EMBER_MAX_REQUEST_LENGTH env var must override the default."""
    model_dir = _isolate_limit_config(monkeypatch, tmp_path)
    monkeypatch.setenv("EMBER_MAX_REQUEST_LENGTH", "16384")
    resolved = limits.from_config(model_dir, "flash")
    assert resolved.max_request_length == 16384
    assert resolved.max_request_length_source is LimitSource.OPERATOR


def test_max_request_length_zero_means_no_cap(monkeypatch, tmp_path):
    """D-002: EMBER_MAX_REQUEST_LENGTH=0 must resolve to 0 (no cap)."""
    model_dir = _isolate_limit_config(monkeypatch, tmp_path)
    monkeypatch.setenv("EMBER_MAX_REQUEST_LENGTH", "0")
    resolved = limits.from_config(model_dir, "flash")
    assert resolved.max_request_length == 0
    assert resolved.max_request_length_source is LimitSource.OPERATOR


def test_engine_accepts_max_request_length_param(monkeypatch, tmp_path):
    """D-002: Engine.__init__ must take the per-request cap, through ``limits``."""
    import inspect

    sig = inspect.signature(runtime.Engine.__init__)
    assert "limits" in sig.parameters, "Engine.__init__ must accept limits"
    assert "max_request_length" in Limits.model_fields


def _counting_engine(monkeypatch, tmp_path, js, engine_limits):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"text_config": {"max_position_embeddings": 262144}})
    )
    processor = SimpleNamespace(tokenizer=object())
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), processor))
    monkeypatch.setattr(runtime, "joint_module", lambda *a, **kw: js)
    return runtime.Engine(model_dir, limits=engine_limits)


def _png_data_uri() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (220, 30, 30)).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


QUESTIONS = {"urgent": {"type": "noul"}}


def test_engine_token_cap_rejects_over_limit(monkeypatch, tmp_path):
    """D-002: advise must raise RequestTooLargeError when input exceeds the cap."""
    engine = _counting_engine(monkeypatch, tmp_path, FakeJointModule(), _limits(50))
    with pytest.raises(runtime.RequestTooLargeError, match="50"):
        engine.advise("x" * 60, {})


def test_engine_token_cap_error_mentions_actual_length(monkeypatch, tmp_path):
    """D-002: the rejection error must name both the cap and the actual token count."""
    engine = _counting_engine(monkeypatch, tmp_path, FakeJointModule(), _limits(100))
    with pytest.raises(ValueError, match="200 tokens exceeds the 100-token"):
        engine.advise("x" * 195, {})


def test_engine_token_cap_accepts_under_limit(monkeypatch, tmp_path):
    """D-002: advise must succeed when the encoded request is within the cap."""
    js = FakeJointModule()
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(50))
    result = engine.advise("x" * 25, {})
    assert result["usage"]["input_tokens"] == 30
    assert len(js.systemone_calls) == 1


def test_engine_token_cap_zero_disables_cap(monkeypatch, tmp_path):
    """D-002: max_request_length=0 disables the cap; the effective maximum applies."""
    js = FakeJointModule()
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(0))
    result = engine.advise("x" * 40000, {})
    assert result["usage"]["input_tokens"] == 40005
    assert js.systemone_calls[0]["max_length"] == 262144


def test_engine_token_cap_error_mentions_env_var(monkeypatch, tmp_path):
    """D-002: rejection error must mention EMBER_MAX_REQUEST_LENGTH."""
    engine = _counting_engine(monkeypatch, tmp_path, FakeJointModule(), _limits(50))
    with pytest.raises(ValueError, match="EMBER_MAX_REQUEST_LENGTH"):
        engine.advise("x" * 60, {})


# ###########################################################################
# Full counting: refuse or serve on the encoded request (FR-004 to FR-007)
# ###########################################################################
def test_a_request_at_the_enforced_limit_is_served(monkeypatch, tmp_path):
    total = record_length({"state": "x" * 100, "questions": QUESTIONS})
    js = FakeJointModule()
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(total))
    result = engine.advise("x" * 100, QUESTIONS)
    assert result["usage"]["input_tokens"] == total


def test_a_request_one_token_over_the_enforced_limit_is_refused(monkeypatch, tmp_path):
    total = record_length({"state": "x" * 100, "questions": QUESTIONS})
    js = FakeJointModule()
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(total - 1))
    with pytest.raises(runtime.RequestTooLargeError):
        engine.advise("x" * 100, QUESTIONS)
    assert js.systemone_calls == []


def test_the_smaller_of_cap_and_maximum_is_enforced(monkeypatch, tmp_path):
    js = FakeJointModule()
    engine_limits = _limits(100, max_length=60)
    engine = _counting_engine(monkeypatch, tmp_path, js, engine_limits)
    with pytest.raises(runtime.RequestTooLargeError) as excinfo:
        engine.advise("x" * 60, {})
    assert "60-token maximum length (EMBER_MAX_LENGTH)" in str(excinfo.value)


def test_a_disabled_cap_still_enforces_a_lowered_maximum(monkeypatch, tmp_path):
    engine_limits = Limits(
        max_length=60,
        max_length_source=LimitSource.OPERATOR,
        max_request_length=0,
        max_request_length_source=LimitSource.OPERATOR,
    )
    engine = _counting_engine(monkeypatch, tmp_path, FakeJointModule(), engine_limits)
    with pytest.raises(runtime.RequestTooLargeError) as excinfo:
        engine.advise("x" * 60, {})
    message = str(excinfo.value)
    assert "60-token maximum length (EMBER_MAX_LENGTH)" in message
    assert message.endswith("up to the model's 262144 tokens.")


def test_the_refusal_carries_its_size_and_limits(monkeypatch, tmp_path):
    engine_limits = _limits(50)
    engine = _counting_engine(monkeypatch, tmp_path, FakeJointModule(), engine_limits)
    with pytest.raises(runtime.RequestTooLargeError) as excinfo:
        engine.advise("x" * 60, QUESTIONS)
    error = excinfo.value
    assert error.size == RequestSize(total=68, state=60, media=0, fixed=8)
    assert error.limits == engine_limits
    assert str(error) == refusal_message(error.size, engine_limits, 262144)


def test_a_per_call_max_length_lowers_the_enforced_limit(monkeypatch, tmp_path):
    js = FakeJointModule()
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(1000))
    with pytest.raises(runtime.RequestTooLargeError, match="50-token"):
        engine.advise("x" * 60, {}, max_length=50)
    engine.advise("x" * 40, {}, max_length=50)
    assert js.systemone_calls[-1]["max_length"] == 50


def test_a_malformed_request_skips_the_check_and_surfaces_systemone_error(
    monkeypatch, tmp_path
):
    def reject(*args: object) -> dict:
        raise ValueError("team: criteria must not be empty")

    js = FakeJointModule(systemone=reject, encode_error=KeyError("criteria"))
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(50))
    with pytest.raises(ValueError, match="criteria must not be empty"):
        engine.advise("x" * 60, {"team": {"type": "choice"}})


def test_a_joint_module_without_encode_record_is_a_contract_error(
    monkeypatch, tmp_path
):
    js = SimpleNamespace(systemone=lambda *a, **kw: {"answers": {}, "usage": {}})
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(50))
    with pytest.raises(RuntimeError, match="encode_record"):
        engine.advise("state", {})


def test_an_answer_from_a_shortened_input_is_never_returned(
    monkeypatch, tmp_path, caplog
):
    def shortened(model: object, processor: object, request: dict, max_length: int):
        tokens = record_length(request) - 1
        return {"answers": {}, "usage": {"input_tokens": tokens, "output_tokens": 0}}

    js = FakeJointModule(systemone=shortened)
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(0))
    with caplog.at_level(logging.ERROR, logger="ember.serving.runtime"):
        with pytest.raises(RuntimeError, match="size check mismatch"):
            engine.advise("state", {})
    assert [record.levelno for record in caplog.records] == [logging.ERROR]


def test_media_kwargs_are_checked_before_counting(monkeypatch, tmp_path):
    js = FakeJointModule()
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(50))
    with pytest.raises(ValueError, match="not permitted"):
        engine.advise("state", {}, media_kwargs={"text": "override"})
    assert js.encode_calls == []


def test_media_kwargs_are_checked_before_any_media_is_decoded(monkeypatch, tmp_path):
    engine = _counting_engine(monkeypatch, tmp_path, FakeJointModule(), _limits(50))
    undecodable = "data:image/png;base64,AAAA"
    with pytest.raises(ValueError, match="not permitted"):
        engine.advise("state", {}, images=[undecodable], media_kwargs={"text": "x"})


def test_media_are_decoded_before_counting(monkeypatch, tmp_path):
    js = FakeJointModule()
    engine = _counting_engine(monkeypatch, tmp_path, js, _limits(0))
    engine.advise("state", {}, images=[_png_data_uri()])
    assert isinstance(js.encode_calls[0]["record"]["images"][0], Image.Image)


# ###########################################################################
# R-004: cmd_model_rm must write an audit entry to stderr
# ###########################################################################
def test_model_rm_writes_audit_entry_to_stderr(tmp_path, monkeypatch, capsys):
    """R-004: cmd_model_rm must emit an audit entry to stderr so there is a
    persistent record of destructive model lifecycle operations that survives
    regardless of the root logger level in normal CLI use."""
    import argparse

    from ember.commands.models import cmd_model_rm

    model_dir = tmp_path / "clef-flash"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(models, "_repo_root", lambda: tmp_path)

    args = argparse.Namespace(name="flash", yes=True)
    ret = cmd_model_rm(args)

    assert ret == 0
    err = capsys.readouterr().err
    assert "flash" in err.lower() or "remov" in err.lower(), (
        "R-004: cmd_model_rm must write an audit entry to stderr"
    )
