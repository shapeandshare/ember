"""Unit tests for the extracted ``ember/commands/`` subcommand handlers.

These mirror the call paths the CLI exercises; each test patches the boundary
the handler calls (the models registry, the process lifecycle, the eval
harness) so no model or server is started.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import types
from pathlib import Path

import ember.mcp
import ember.serving
import pytest
from ember import cli
from ember import models as models_mod
from ember.cfg import paths
from ember.commands import agents as agents_cmd
from ember.commands import config as config_cmd
from ember.commands import doctor as doctor_cmd
from ember.commands import endpoint as endpoint_cmd
from ember.commands import eval as eval_cmd
from ember.commands import lifecycle
from ember.commands import models as models_cmd


@pytest.fixture(autouse=True)
def _restore_environment():
    """Handlers assign ``os.environ`` directly; restore it after every test."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    for name in ("EMBER_SERVER_URL", "EMBER_HOST", "EMBER_PORT", "EMBER_MODEL"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def _ns(**kw):
    return argparse.Namespace(**kw)


def _stub(monkeypatch, package, name, main):
    """Replace a lazily-imported submodule with a stub, package attr included."""
    stub = types.ModuleType(f"{package.__name__}.{name}")
    stub.main = main
    monkeypatch.setitem(sys.modules, f"{package.__name__}.{name}", stub)
    monkeypatch.setattr(package, name, stub, raising=False)
    return stub


# ###########################################################################
# cli.main dispatch
# ###########################################################################
def test_main_returns_130_on_keyboard_interrupt(monkeypatch):
    def raiser(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "cmd_config_path", raiser)
    assert cli.main(["config", "path"]) == 130


def test_main_returns_1_and_prints_error_on_runtime_error(monkeypatch, capsys):
    def raiser(_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "cmd_config_path", raiser)
    assert cli.main(["config", "path"]) == 1
    assert "error: boom" in capsys.readouterr().err


def test_main_rejects_extra_args_for_non_agent_commands():
    with pytest.raises(SystemExit):
        cli.main(["status", "--definitely-not-a-flag"])


def test_main_forwards_extra_args_to_the_agent_command(monkeypatch):
    captured: list[list[str]] = []
    module = types.ModuleType("evals.eval.run_agent_evals")
    module.main = lambda argv: captured.append(list(argv)) or 0
    monkeypatch.setitem(sys.modules, "evals.eval.run_agent_evals", module)

    assert cli.main(["eval", "agent", "--models", "x"]) == 0
    assert captured
    assert "--models" in captured[0]


# ###########################################################################
# model commands
# ###########################################################################
def test_model_pull_reports_path(monkeypatch, capsys):
    monkeypatch.setattr(
        models_mod, "pull", lambda name, allow_low_disk=False: Path("/m")
    )
    assert models_cmd.cmd_model_pull(_ns(name="flash", allow_low_disk=True)) == 0
    assert "/m" in capsys.readouterr().out


def test_model_list_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(models_mod, "list_models", lambda: [{"name": "flash"}])
    assert models_cmd.cmd_model_list(_ns()) == 0
    assert json.loads(capsys.readouterr().out) == [{"name": "flash"}]


def test_model_path_reports_pulled(monkeypatch, capsys):
    monkeypatch.setattr(models_mod, "resolve_dir", lambda name: Path("/models/flash"))
    assert models_cmd.cmd_model_path(_ns(name="flash")) == 0
    assert "/models/flash" in capsys.readouterr().out


def test_model_path_reports_not_pulled(monkeypatch, capsys):
    monkeypatch.setattr(models_mod, "resolve_dir", lambda name: None)
    assert models_cmd.cmd_model_path(_ns(name="flash")) == 1
    assert "not pulled" in capsys.readouterr().out


def test_model_rm_aborts_when_declined(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    assert models_cmd.cmd_model_rm(_ns(name="flash", yes=False)) == 1
    assert "aborted" in capsys.readouterr().out


def test_model_rm_removes_with_yes(monkeypatch, capsys):
    monkeypatch.setattr(models_mod, "remove", lambda name: f"removed {name}")
    assert models_cmd.cmd_model_rm(_ns(name="flash", yes=True)) == 0
    assert "removed flash" in capsys.readouterr().out


# ###########################################################################
# lifecycle commands
# ###########################################################################
def test_host_port_prefers_args_over_config():
    assert lifecycle.host_port(_ns(host="1.2.3.4", port=9999)) == ("1.2.3.4", 9999)


def test_cmd_start_reports_pid(monkeypatch, capsys):
    monkeypatch.setattr(lifecycle.process, "start", lambda *a: 4321)
    assert lifecycle.cmd_start(_ns(model=None, host=None, port=None, device=None)) == 0
    assert "4321" in capsys.readouterr().out


def test_cmd_restart_reports_pid(monkeypatch, capsys):
    monkeypatch.setattr(lifecycle.process, "restart", lambda *a: 4322)
    assert (
        lifecycle.cmd_restart(_ns(model=None, host=None, port=None, device=None)) == 0
    )
    assert "4322" in capsys.readouterr().out


def test_cmd_stop_reports_stopped(monkeypatch, capsys):
    monkeypatch.setattr(lifecycle.process, "stop", lambda *a: True)
    assert lifecycle.cmd_stop(_ns(host=None, port=None)) == 0
    assert "stopped" in capsys.readouterr().out


def test_cmd_stop_reports_not_running(monkeypatch, capsys):
    monkeypatch.setattr(lifecycle.process, "stop", lambda *a: False)
    monkeypatch.setattr(lifecycle.process, "health", lambda *a: None)
    assert lifecycle.cmd_stop(_ns(host=None, port=None)) == 0
    assert "not running" in capsys.readouterr().out


def test_cmd_stop_flags_a_foreign_server(monkeypatch, capsys):
    monkeypatch.setattr(lifecycle.process, "stop", lambda *a: False)
    monkeypatch.setattr(lifecycle.process, "health", lambda *a: {"pid": 7})
    assert lifecycle.cmd_stop(_ns(host=None, port=None)) == 1
    assert "not started by" in capsys.readouterr().out


def test_cmd_logs_without_a_log_returns_1(monkeypatch, capsys):
    monkeypatch.setattr(paths, "server_log_path", lambda: Path("/nope/server.log"))
    assert lifecycle.cmd_logs(_ns(lines=10)) == 1
    assert "no log yet" in capsys.readouterr().out


def test_cmd_serve_sets_env_and_runs_server(sandbox, monkeypatch):
    monkeypatch.setattr(models_mod, "resolve_dir", lambda name: sandbox / "m")
    ran: list[bool] = []
    _stub(monkeypatch, ember.serving, "server", lambda: ran.append(True))

    args = _ns(model="flash", host=None, port=None, device="cpu")
    assert lifecycle.cmd_serve(args) == 0
    assert ran == [True]


def test_cmd_serve_raises_when_model_not_pulled(sandbox, monkeypatch):
    monkeypatch.setattr(models_mod, "resolve_dir", lambda name: None)
    args = _ns(model="flash", host=None, port=None, device=None)
    with pytest.raises(SystemExit, match="is not pulled"):
        lifecycle.cmd_serve(args)


def test_cmd_mcp_sets_client_url_for_a_wildcard_host(monkeypatch):
    _stub(monkeypatch, ember.mcp, "mcp_server", lambda: None)
    args = _ns(host="0.0.0.0", port=8765, device=None, model=None)  # noqa: S104 - test args, not a bind
    assert lifecycle.cmd_mcp(args) == 0
    assert os.environ["EMBER_SERVER_URL"] == "http://127.0.0.1:8765"


# ###########################################################################
# doctor
# ###########################################################################
def test_doctor_platform_reports_unsupported(monkeypatch):
    monkeypatch.setattr(paths, "is_apple_silicon", lambda: False)
    infos: list[tuple[str, str]] = []
    checks: list[str] = []
    doctor_cmd._doctor_check_platform(
        lambda label, good, detail: checks.append(label) or good,
        lambda label, detail: infos.append((label, detail)),
    )
    assert infos
    assert infos[0][0] == "platform"
    assert "platform" not in checks


def test_doctor_deps_reports_missing_torch(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "transformers", None)
    failed: list[str] = []
    result = doctor_cmd._doctor_check_deps(
        lambda label, good, detail: failed.append(label) or good
    )
    assert result is False
    assert "torch" in failed


def test_cmd_doctor_reports_invalid_endpoint(monkeypatch, capsys):
    monkeypatch.setattr(doctor_cmd, "_doctor_check_platform", lambda c, i: True)
    monkeypatch.setattr(doctor_cmd, "_doctor_check_deps", lambda c: True)
    monkeypatch.setattr(doctor_cmd, "_doctor_check_models", lambda c, i: True)
    monkeypatch.setattr(doctor_cmd.process, "health", lambda *a: None)

    from ember.cfg import endpoint as cfg_endpoint

    def boom(_args):
        raise cfg_endpoint.InvalidEndpointError("bad url")

    monkeypatch.setattr(doctor_cmd, "resolve_endpoint", boom)
    assert doctor_cmd.cmd_doctor(_ns(server_url="nope")) == 0
    assert "invalid: bad url" in capsys.readouterr().out


# ###########################################################################
# config
# ###########################################################################
def test_config_path_prints_the_path(monkeypatch, capsys):
    monkeypatch.setattr(paths, "config_path", lambda: Path("/etc/ember.json"))
    assert config_cmd.cmd_config_path(_ns()) == 0
    assert "/etc/ember.json" in capsys.readouterr().out


# ###########################################################################
# agents: uninstall purge path
# ###########################################################################
def test_uninstall_purges_cached_models(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(agents_cmd.process, "stop", lambda: False)
    monkeypatch.setattr(
        agents_cmd.models_mod,
        "list_models",
        lambda: [{"name": "flash", "cached": True}, {"name": "full", "cached": False}],
    )
    removed: list[str] = []
    monkeypatch.setattr(
        agents_cmd.models_mod, "remove", lambda name: removed.append(name) or "gone"
    )
    args = _ns(purge_models=True)
    assert agents_cmd.cmd_uninstall(args) == 0
    assert removed == ["flash"]


# ###########################################################################
# endpoint
# ###########################################################################
def test_remote_health_returns_none_on_http_error(monkeypatch):
    from ember.cfg.endpoint import Endpoint

    def boom(*_a, **_kw):
        raise endpoint_cmd.httpx.HTTPError("nope")

    monkeypatch.setattr(endpoint_cmd.httpx, "get", boom)
    ep = Endpoint(
        url="https://x",
        host="x",
        scheme="https",
        is_local=False,
        allow_insecure_transport=False,
        request_timeout=1.0,
    )
    assert endpoint_cmd.remote_health(ep) is None


def test_cmd_mcp_sets_device_and_model_env(monkeypatch):
    _stub(monkeypatch, ember.mcp, "mcp_server", lambda: None)
    args = _ns(host=None, port=None, device="cpu", model="full")
    assert lifecycle.cmd_mcp(args) == 0
    assert os.environ["EMBER_DEVICE"] == "cpu"
    assert os.environ["EMBER_MODEL"] == "full"


def test_remote_health_returns_none_on_non_200(monkeypatch):
    from ember.cfg.endpoint import Endpoint

    class FakeResp:
        status_code = 500

    monkeypatch.setattr(endpoint_cmd.httpx, "get", lambda *a, **kw: FakeResp())
    ep = Endpoint(
        url="https://x",
        host="x",
        scheme="https",
        is_local=False,
        allow_insecure_transport=False,
        request_timeout=1.0,
    )
    assert endpoint_cmd.remote_health(ep) is None


# ###########################################################################
# eval command argv building
# ###########################################################################
def test_eval_run_passes_options(monkeypatch):
    module = types.ModuleType("evals.eval.run_evals")
    module.DEFAULT_SERVER = "http://default"
    seen: dict = {}

    def fake_run(server, **kw):
        seen["server"] = server
        seen.update(kw)
        return 0

    module.run_evals = fake_run
    monkeypatch.setitem(sys.modules, "evals.eval.run_evals", module)
    args = _ns(
        server=None, split="dev", category="routing", dry_run=True, dataset="d.jsonl"
    )
    assert eval_cmd.cmd_eval_run(args) == 0
    assert seen["split"] == "dev"
    assert seen["dry_run"] is True


def test_eval_report_builds_argv(monkeypatch):
    module = types.ModuleType("evals.eval.report_evals")
    captured: list[list[str]] = []
    module.main = lambda argv: captured.append(list(argv)) or 0
    monkeypatch.setitem(sys.modules, "evals.eval.report_evals", module)
    args = _ns(
        results_file=Path("r.json"), format="html", compare=[Path("a"), Path("b")]
    )
    assert eval_cmd.cmd_eval_report(args) == 0
    assert captured == [["r.json", "--format", "html", "--compare", "a", "b"]]


def test_eval_export_builds_argv(monkeypatch):
    module = types.ModuleType("evals.eval.report_evals")
    captured: list[list[str]] = []
    module.main = lambda argv: captured.append(list(argv)) or 0
    monkeypatch.setitem(sys.modules, "evals.eval.report_evals", module)
    args = _ns(results_file=Path("r.json"), out=Path("out"), agent=Path("agent"))
    assert eval_cmd.cmd_eval_export(args) == 0
    assert captured == [["--export", "r.json", "--out", "out", "--agent", "agent"]]


def test_eval_snapshot_builds_argv(monkeypatch):
    module = types.ModuleType("evals.eval.snapshot_evals")
    captured: list[list[str]] = []
    module.main = lambda argv: captured.append(list(argv)) or 0
    monkeypatch.setitem(sys.modules, "evals.eval.snapshot_evals", module)
    assert eval_cmd.cmd_eval_snapshot(_ns(results_file=Path("r.json"))) == 0
    assert captured == [["r.json"]]
