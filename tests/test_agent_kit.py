"""The onboarding kit is the agent-facing contract; these tests pin its shape."""

from __future__ import annotations

import re
from pathlib import Path

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


# ###########################################################################
# Size limits (contracts/agent-kit.md, FR-008, SC-005)
# ###########################################################################
REPO = Path(__file__).resolve().parents[1]


def _caps() -> list[str]:
    from ember import models
    from ember.serving.limits import default_request_cap

    names = [*models.REGISTRY, None]
    return [f"{default_request_cap(name)[0]:,}" for name in names]


def _sample_refusal() -> str:
    from ember.serving.limit_source import LimitSource
    from ember.serving.limits import Limits
    from ember.serving.request_size import RequestSize, refusal_message

    limits = Limits(
        max_length=262144,
        max_length_source=LimitSource.MODEL,
        max_request_length=32768,
        max_request_length_source=LimitSource.FALLBACK,
    )
    return refusal_message(
        RequestSize(total=41230, state=39800, media=0, fixed=1430), limits, 262144
    )


def test_instructions_say_over_cap_requests_are_refused_not_truncated():
    from ember.serving.limits import default_request_cap

    text = agent_kit.instructions()
    assert len(text.encode("utf-8")) <= 2048
    assert "refused" in text
    assert "never truncated" in text
    assert f"{default_request_cap('flash')[0]:,}" in text


def test_skill_states_every_default_cap_and_why_it_holds():
    text = agent_kit.skill()
    for cap in _caps():
        assert cap in text
    for word in ("refused", "split", "measured", "fallback"):
        assert word in text
    assert "262,144-token window" not in text


def test_skill_quotes_only_fragments_of_the_real_refusal():
    text = agent_kit.skill()
    message = _sample_refusal()
    for fragment in ("request too large:", "Split: state"):
        assert fragment in text
        assert fragment in message


def test_snippet_says_refused_requests_trim_the_largest_part():
    text = agent_kit.snippet()
    assert "refused" in text
    assert "largest part" in text


def test_readme_and_compatibility_state_every_registered_cap():
    from ember import models
    from ember.serving.limits import default_request_cap

    readme = next(
        line
        for line in (REPO / "README.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| `EMBER_MAX_REQUEST_LENGTH`")
    )
    compat = (REPO / "COMPATIBILITY.md").read_text(encoding="utf-8")
    bullet = compat.split("- **Context length.**", 1)[1].split("\n- **", 1)[0]
    for name in models.REGISTRY:
        cap = f"{default_request_cap(name)[0]:,}"
        assert cap in readme
        assert cap in bullet
    assert "refused" in readme
    assert "refused" in bullet
