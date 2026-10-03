"""CLI onboarding paths: `clef agents show|install` and `clef init --opencode`.

Every test runs in a temporary directory with HOME redirected, so nothing touches
the real project or user config.
"""

from __future__ import annotations

import json

import pytest

from clef_local import agent_kit, cli


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path


@pytest.mark.parametrize(
    ("what", "loader"),
    [("instructions", agent_kit.instructions), ("skill", agent_kit.skill), ("snippet", agent_kit.snippet)],
)
def test_agents_show_prints_the_kit(what, loader, capsys):
    assert cli.main(["agents", "show", what]) == 0
    assert capsys.readouterr().out.strip() == loader().strip()


@pytest.mark.parametrize(
    ("agent", "root"),
    [("opencode", ".opencode/skills"), ("claude", ".claude/skills"), ("codex", ".agents/skills")],
)
def test_agents_install_writes_project_skill(sandbox, agent, root):
    assert cli.main(["agents", "install", "--agent", agent]) == 0
    assert (sandbox / root / "clef-decide/SKILL.md").read_text() == agent_kit.skill()


def test_agents_install_global_targets_home(sandbox):
    assert cli.main(["agents", "install", "--agent", "opencode", "--global"]) == 0
    assert (sandbox / "home/.config/opencode/skills/clef-decide/SKILL.md").exists()


def test_init_opencode_registers_server_plugin_and_skill(sandbox):
    assert cli.main(["init", "--opencode"]) == 0
    config = json.loads((sandbox / "opencode.json").read_text())
    assert config["mcp"]["clef"]["type"] == "local"
    assert (sandbox / ".opencode/plugins/clef.js").exists()
    assert (sandbox / ".opencode/skills/clef-decide/SKILL.md").read_text() == agent_kit.skill()
