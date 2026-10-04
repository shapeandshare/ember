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
from ember import (
    agent_kit,
    cli,
    models,
    opencode_config,
    opencode_plugin,
    process,
)

from tests.conftest import free_port


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
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


def test_status_and_stop_are_inert_on_an_unused_port(sandbox, capsys):
    port = str(free_port())
    assert cli.main(["status", "--port", port]) == 1
    assert cli.main(["stop", "--port", port]) == 0
    assert capsys.readouterr().out.splitlines() == ["not running", "not running"]


def test_doctor_treats_a_stopped_server_as_information(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(models, "resolve_dir", lambda *args, **kwargs: sandbox)
    monkeypatch.setattr(process, "health", lambda *args, **kwargs: None)
    assert cli.main(["doctor"]) == 0
    assert "[info] server: stopped" in capsys.readouterr().out


def test_uninstall_removes_global_installs_and_keeps_other_config(sandbox):
    assert cli.main(["init", "--opencode", "--global"]) == 0
    global_config = opencode_config.global_config_path()
    config = json.loads(global_config.read_text())
    config["model"] = "keep-me"
    global_config.write_text(json.dumps(config))

    assert cli.main(["uninstall"]) == 0
    assert not (
        opencode_plugin.plugin_dir("global") / opencode_plugin.PLUGIN_FILENAME
    ).exists()
    assert not agent_kit.skill_path("opencode", "global").exists()
    remaining = json.loads(global_config.read_text())
    assert remaining["model"] == "keep-me"
    assert "ember" not in remaining["mcp"]


def test_eval_commands_require_a_checkout(monkeypatch):
    monkeypatch.setitem(sys.modules, "scripts", None)
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
