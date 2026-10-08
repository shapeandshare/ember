"""CLI paths: onboarding (`agents`, `init --opencode`), lifecycle on an unused port,
`doctor`, and `uninstall`.

Every test runs in a temporary directory with HOME and the state dir redirected, so
nothing touches the real project, user config, or running servers.
"""

from __future__ import annotations

import argparse
import json
import sys

import pytest
from ember import cli, models
from ember.agent_kit import api as agent_kit
from ember.commands import endpoint as endpoint_cmd
from ember.commands import lifecycle
from ember.kilocode import kilocode_config
from ember.opencode import opencode_config, opencode_plugin
from ember.serving import process

from tests.conftest import free_port


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    for name in (
        "EMBER_SERVER_URL",
        "EMBER_AUTH_TOKEN",
        "EMBER_AUTH_HEADER",
        "EMBER_ALLOW_INSECURE_TRANSPORT",
        "EMBER_REQUEST_TIMEOUT",
        "EMBER_SERVER_AUTH_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


@pytest.mark.parametrize(
    ("what", "loader"),
    [
        ("instructions", agent_kit.instructions),
        ("skill", agent_kit.skill),
        ("snippet", agent_kit.snippet),
    ],
)
def test_agents_show_prints_the_kit(what, loader, capsys):
    assert cli.main(["agents", "show", what]) == 0
    assert capsys.readouterr().out.strip() == loader().strip()


@pytest.mark.parametrize(
    ("agent", "root"),
    [
        ("opencode", ".opencode/skills"),
        ("claude", ".claude/skills"),
        ("codex", ".agents/skills"),
        ("kilocode", ".kilo/skills"),
    ],
)
def test_agents_install_writes_project_skill(sandbox, agent, root):
    assert cli.main(["agents", "install", "--agent", agent]) == 0
    assert (sandbox / root / "ember-advise/SKILL.md").read_text() == agent_kit.skill()


def test_agents_install_global_targets_home(sandbox):
    assert cli.main(["agents", "install", "--agent", "opencode", "--global"]) == 0
    assert (sandbox / "home/.config/opencode/skills/ember-advise/SKILL.md").exists()


def test_init_opencode_registers_server_plugin_and_skill(sandbox):
    assert cli.main(["init", "--opencode"]) == 0
    config = json.loads((sandbox / "opencode.json").read_text())
    assert config["mcp"]["ember"]["type"] == "local"
    assert config["mcp"]["vault"]["command"][-1] == "vault"
    assert (sandbox / ".opencode/plugins/ember.js").exists()
    assert (
        sandbox / ".opencode/skills/ember-advise/SKILL.md"
    ).read_text() == agent_kit.skill()


def test_init_kilocode_registers_server_and_skill(sandbox):
    assert cli.main(["init", "--kilocode"]) == 0
    config = json.loads((sandbox / "kilo.json").read_text())
    assert config["mcp"]["ember"]["type"] == "local"
    assert (
        sandbox / ".kilo/skills/ember-advise/SKILL.md"
    ).read_text() == agent_kit.skill()


def test_init_kilocode_with_server_url_bootstraps_a_remote_endpoint(sandbox):
    assert (
        cli.main(
            [
                "init",
                "--kilocode",
                "--server-url",
                "https://decisions.example.com",
                "--auth-header",
                "X-API-KEY",
            ]
        )
        == 0
    )
    config = json.loads((sandbox / "kilo.json").read_text())
    env = config["mcp"]["ember"]["environment"]
    assert env["EMBER_SERVER_URL"] == "https://decisions.example.com"
    assert env["EMBER_AUTH_HEADER"] == "X-API-KEY"
    assert "EMBER_AUTH_TOKEN" not in env
    assert "token" not in (sandbox / "kilo.json").read_text().lower()


def test_init_opencode_with_server_url_bootstraps_a_remote_endpoint(sandbox):
    assert (
        cli.main(
            ["init", "--opencode", "--server-url", "https://decisions.example.com"]
        )
        == 0
    )
    config = json.loads((sandbox / "opencode.json").read_text())
    env = config["mcp"]["ember"]["environment"]
    assert env["EMBER_SERVER_URL"] == "https://decisions.example.com"


def test_status_and_stop_are_inert_on_an_unused_port(sandbox, capsys):
    port = str(free_port())
    assert cli.main(["status", "--port", port]) == 1
    assert cli.main(["stop", "--port", port]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == "not running"
    assert '"reachable": false' in out


def test_status_reports_local_endpoint(sandbox, capsys):
    port = str(free_port())
    assert cli.main(["status", "--port", port]) == 1
    body = json.loads(capsys.readouterr().out)
    assert body["kind"] == "local"
    assert body["reachable"] is False


def test_status_reports_remote_endpoint(sandbox, capsys):
    assert cli.main(["status", "--server-url", "https://example.invalid"]) == 1
    body = json.loads(capsys.readouterr().out)
    assert body["kind"] == "remote"
    assert body["reachable"] is False


def test_status_surfaces_remote_health_fields(sandbox, capsys, monkeypatch):
    from ember.cfg import endpoint as ep

    remote = ep.Endpoint(
        url="https://decisions.example",
        host="decisions.example",
        scheme="https",
        is_local=False,
        allow_insecure_transport=False,
        request_timeout=5,
    )
    monkeypatch.setattr(lifecycle, "resolve_endpoint", lambda args: remote)
    monkeypatch.setattr(
        endpoint_cmd,
        "remote_health",
        lambda endpoint: {"status": "ok", "version": "9.9.9", "auth_required": True},
    )
    assert cli.main(["status"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["kind"] == "remote"
    assert body["reachable"] is True
    assert body["contract_version"] == "9.9.9"
    assert body["remote_auth_required"] is True
    assert body["auth_configured"] is False


def test_status_rejects_plaintext_remote(sandbox, capsys):
    assert cli.main(["status", "--server-url", "http://192.0.2.1:8765"]) == 1
    assert "[fail]" in capsys.readouterr().out


def test_local_to_remote_is_single_reversible_change(sandbox, capsys):
    assert cli.main(["status", "--server-url", "https://example.invalid"]) == 1
    assert json.loads(capsys.readouterr().out)["kind"] == "remote"
    port = str(free_port())
    assert cli.main(["status", "--port", port]) == 1
    assert json.loads(capsys.readouterr().out)["kind"] == "local"


def test_doctor_labels_a_configured_anaconda_hosted_endpoint_as_remote(
    sandbox, monkeypatch, capsys
):
    """US3 T019: spec FR-005/SC-004; contracts/hosted-endpoint.md rule 7 — this is a
    regression lock proving the existing (001) endpoint-status reporting already
    distinguishes remote from local with no new code needed for an Anaconda-hosted
    endpoint, which is just another non-loopback server_url."""
    monkeypatch.setattr(models, "resolve_dir", lambda *args, **kwargs: sandbox)
    monkeypatch.setattr(process, "health", lambda *args, **kwargs: None)
    assert cli.main(["doctor", "--server-url", "https://anaconda-hosted.example"]) == 0
    out = capsys.readouterr().out
    assert "[info] endpoint: remote https://anaconda-hosted.example" in out


def test_doctor_labels_the_default_loopback_endpoint_as_local(
    sandbox, monkeypatch, capsys
):
    """US3 T019 (counterpart): no endpoint configured -> local, unambiguous."""
    monkeypatch.setattr(models, "resolve_dir", lambda *args, **kwargs: sandbox)
    monkeypatch.setattr(process, "health", lambda *args, **kwargs: None)
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "[info] endpoint: local http://127.0.0.1:8765" in out


def test_doctor_makes_no_remote_http_call_when_unconfigured(
    sandbox, monkeypatch, capsys
):
    """US3 T021: spec SC-005 — an unconfigured install must never reach
    endpoint_cmd.remote_health (the only outbound-to-a-remote-host call on this
    path); only the local loopback process.health probe may run."""
    monkeypatch.setattr(models, "resolve_dir", lambda *args, **kwargs: sandbox)
    monkeypatch.setattr(process, "health", lambda *args, **kwargs: None)

    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(
            "remote_health must not be called for an unconfigured (local) endpoint"
        )

    monkeypatch.setattr(endpoint_cmd, "remote_health", _fail_if_called)
    assert cli.main(["doctor"]) == 0


def test_config_show_masks_secrets(sandbox, capsys, monkeypatch):
    monkeypatch.setenv("EMBER_AUTH_TOKEN", "topsecret")
    monkeypatch.setenv("EMBER_SERVER_AUTH_TOKEN", "server-token")
    monkeypatch.setenv("EMBER_ANACONDA_S3_ACCESS_KEY_ID", "AKIAFAKE")
    monkeypatch.setenv("EMBER_ANACONDA_S3_SECRET_ACCESS_KEY", "fakesecretkey")
    assert cli.main(["config", "show"]) == 0
    out = capsys.readouterr().out
    assert "topsecret" not in out
    assert "server-token" not in out
    assert "AKIAFAKE" not in out
    assert "fakesecretkey" not in out
    body = json.loads(out)
    assert body["auth_token"] == "***"
    assert body["server_auth_token"] == "***"
    assert body["anaconda_s3_access_key_id"] == "***"
    assert body["anaconda_s3_secret_access_key"] == "***"


def test_config_show_reflects_env_var_overrides_for_every_key(
    sandbox, capsys, monkeypatch
):
    """Critical review finding (2026-10-08): `ember config show` only applied
    env-var precedence to `server_url` and the four masked secret keys —
    every other DEFAULTS key (including `anaconda_s3_region`) silently showed
    its config-file/default value even when overridden by an EMBER_* env
    var, with no visible indication the override was being ignored.
    `config.resolve()` already implements the correct flag > env > file >
    default precedence; `cmd_config_show` MUST use it for every key, not
    just a hardcoded subset."""
    monkeypatch.setenv("EMBER_HOST", "192.0.2.1")
    monkeypatch.setenv("EMBER_ANACONDA_S3_REGION", "us-west-2")
    assert cli.main(["config", "show"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["host"] == "192.0.2.1"
    assert body["anaconda_s3_region"] == "us-west-2"


def test_doctor_treats_a_stopped_server_as_information(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(models, "resolve_dir", lambda *args, **kwargs: sandbox)
    monkeypatch.setattr(process, "health", lambda *args, **kwargs: None)
    assert cli.main(["doctor"]) == 0
    assert "[info] server: stopped" in capsys.readouterr().out


def test_doctor_defaults_to_flash_when_unconfigured(sandbox, monkeypatch, capsys):
    """An unconfigured install resolves to the default registry entry."""
    monkeypatch.delenv("EMBER_MODEL", raising=False)
    monkeypatch.setattr(models, "resolve_dir", lambda *args, **kwargs: sandbox)
    monkeypatch.setattr(process, "health", lambda *args, **kwargs: None)
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert models.DEFAULT == "flash"
    assert f"[ok] model {models.DEFAULT}:" in out


def test_doctor_respects_explicit_flash_override(sandbox, monkeypatch, capsys):
    """Spec FR-003/FR-011; contracts/model-registry.md rule 11: explicit choice wins."""
    monkeypatch.setenv("EMBER_MODEL", "flash")
    monkeypatch.setattr(models, "resolve_dir", lambda *args, **kwargs: sandbox)
    monkeypatch.setattr(process, "health", lambda *args, **kwargs: None)
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "model flash" in out


def test_doctor_reports_the_hosted_s3_uri_when_configured(sandbox, monkeypatch, capsys):
    """When EMBER_MODEL_S3_URI is configured (constitution Article V, "Model
    Loading"), doctor reports that location instead of a REGISTRY entry."""
    from ember.serving import hosted

    fake_source = hosted.HostedModelSource(
        uri="s3://my-bucket/clef-flash", model_dir=sandbox
    )
    monkeypatch.setattr(hosted, "resolve", lambda: fake_source)
    monkeypatch.setattr(process, "health", lambda *args, **kwargs: None)
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "s3://my-bucket/clef-flash" in out


def test_uninstall_removes_global_installs_and_keeps_other_config(sandbox):
    assert cli.main(["init", "--opencode", "--global"]) == 0
    assert cli.main(["init", "--kilocode", "--global"]) == 0
    global_config = opencode_config.global_config_path()
    config = json.loads(global_config.read_text())
    config["model"] = "keep-me"
    global_config.write_text(json.dumps(config))

    assert cli.main(["uninstall"]) == 0
    assert not (
        opencode_plugin.plugin_dir("global") / opencode_plugin.PLUGIN_FILENAME
    ).exists()
    assert not agent_kit.skill_path("opencode", "global").exists()
    assert not agent_kit.skill_path("kilocode", "global").exists()
    remaining = json.loads(global_config.read_text())
    assert remaining["model"] == "keep-me"
    assert "ember" not in remaining["mcp"]

    kilo_config = kilocode_config.global_config_path()
    assert "ember" not in json.loads(kilo_config.read_text()).get("mcp", {})


def test_eval_commands_require_a_checkout(monkeypatch):
    monkeypatch.setitem(sys.modules, "evals.eval", None)
    monkeypatch.setitem(sys.modules, "evals.eval.run_evals", None)
    monkeypatch.setitem(sys.modules, "evals.eval.report_evals", None)
    args = argparse.Namespace(
        server=None,
        split=None,
        category=None,
        dry_run=True,
        dataset="unused",
        results_file=None,
        format="markdown",
        compare=None,
    )
    with pytest.raises(RuntimeError, match="require a repository checkout"):
        cli.cmd_eval_run(args)
    with pytest.raises(RuntimeError, match="require a repository checkout"):
        cli.cmd_eval_report(args)


def test_resolve_endpoint_uses_http_for_loopback_host() -> None:
    args = argparse.Namespace(server_url=None, host="127.0.0.1", port=9000)
    assert endpoint_cmd.resolve_endpoint(args).url == "http://127.0.0.1:9000"


def test_resolve_endpoint_uses_https_for_remote_host() -> None:
    args = argparse.Namespace(server_url=None, host="ember.example.com", port=9000)
    assert endpoint_cmd.resolve_endpoint(args).url == "https://ember.example.com:9000"


def test_endpoint_resolve_endpoint_uses_http_for_loopback_host() -> None:
    from ember.commands.endpoint import resolve_endpoint

    args = argparse.Namespace(server_url=None, host="127.0.0.1", port=9001)
    assert resolve_endpoint(args).url == "http://127.0.0.1:9001"


def test_endpoint_resolve_endpoint_uses_https_for_remote_host() -> None:
    from ember.commands.endpoint import resolve_endpoint

    args = argparse.Namespace(server_url=None, host="ember.example.com", port=9001)
    assert resolve_endpoint(args).url == "https://ember.example.com:9001"


def test_endpoint_remote_health_returns_none_on_connection_error() -> None:
    from ember.cfg.endpoint import Endpoint
    from ember.commands.endpoint import remote_health

    ep = Endpoint(
        url="http://127.0.0.1:1",
        host="127.0.0.1",
        scheme="http",
        is_local=True,
        allow_insecure_transport=True,
        request_timeout=1.0,
    )
    assert remote_health(ep) is None


def test_endpoint_status_marks_reachable_when_health_returns_body(
    monkeypatch,
) -> None:
    from ember.cfg.endpoint import Endpoint
    from ember.commands import endpoint as ep_mod

    ep = Endpoint(
        url="http://127.0.0.1:1",
        host="127.0.0.1",
        scheme="http",
        is_local=False,
        allow_insecure_transport=True,
        request_timeout=1.0,
    )
    monkeypatch.setattr(
        ep_mod,
        "remote_health",
        lambda _: {"status": "ok", "version": "1.0.0", "auth_required": False},
    )
    status = ep_mod.endpoint_status(ep)
    assert status["reachable"] is True
    assert status["ready"] == "ok"
    assert status["contract_version"] == "1.0.0"
    assert status["remote_auth_required"] is False
