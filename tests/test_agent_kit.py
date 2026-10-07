"""The onboarding kit is the agent-facing contract; these tests pin its shape."""

from __future__ import annotations

import re

import yaml
from ember.agent_kit import api as agent_kit


def _frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    return yaml.safe_load(text.split("---\n", 2)[1])


def test_instructions_fit_claude_code_truncation_limit():
    text = agent_kit.instructions()
    assert len(text.encode("utf-8")) <= 2048
    for needle in (
        "`advise`",
        "ember_advise",
        agent_kit.GUIDE_URI,
        agent_kit.SKILL_NAME,
    ):
        assert needle in text


def test_skill_frontmatter_follows_agent_skills_contract():
    meta = _frontmatter(agent_kit.skill())
    assert meta["name"] == agent_kit.SKILL_NAME
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", meta["name"])
    assert len(meta["name"]) <= 64
    assert 1 <= len(meta["description"]) <= 1024
    assert "ember_advise" in meta["description"]


def test_snippet_points_agents_at_tool_skill_and_guide():
    text = agent_kit.snippet()
    for needle in ("ember_advise", agent_kit.SKILL_NAME, agent_kit.GUIDE_URI):
        assert needle in text


def test_skill_and_snippet_document_media_inputs():
    assert "images" in agent_kit.skill()
    assert "images" in agent_kit.snippet()


def test_skill_paths_per_agent_and_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    expected = {
        ("opencode", "project"): tmp_path / ".opencode/skills/ember-advise/SKILL.md",
        ("claude", "project"): tmp_path / ".claude/skills/ember-advise/SKILL.md",
        ("codex", "project"): tmp_path / ".agents/skills/ember-advise/SKILL.md",
        ("kilocode", "project"): tmp_path / ".kilo/skills/ember-advise/SKILL.md",
        ("opencode", "global"): tmp_path
        / "home/.config/opencode/skills/ember-advise/SKILL.md",
        ("claude", "global"): tmp_path / "home/.claude/skills/ember-advise/SKILL.md",
        ("codex", "global"): tmp_path / "home/.agents/skills/ember-advise/SKILL.md",
        ("kilocode", "global"): tmp_path
        / "home/.config/kilo/skills/ember-advise/SKILL.md",
    }
    for (agent, scope), path in expected.items():
        assert agent_kit.skill_path(agent, scope, tmp_path) == path


def test_install_skill_writes_the_packaged_playbook(tmp_path):
    path = agent_kit.install_skill("codex", "project", tmp_path)
    assert path.read_text(encoding="utf-8") == agent_kit.skill()


def test_kilocode_is_a_first_class_supported_agent():
    assert "kilocode" in agent_kit.AGENTS
