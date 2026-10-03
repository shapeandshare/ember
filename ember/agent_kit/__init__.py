"""Consumer onboarding kit: what coding agents read to use the `advise` tool well.

One source of truth, delivered three ways: MCP `initialize.instructions`, the
`ember://guide` resource plus the installable `ember-advise` skill,
and an AGENTS.md snippet.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

SKILL_NAME = "ember-advise"
GUIDE_URI = "ember://guide"

_SKILL_ROOTS: dict[str, tuple[str, str]] = {
    "opencode": (".opencode/skills", ".config/opencode/skills"),
    "claude": (".claude/skills", ".claude/skills"),
    "codex": (".agents/skills", ".agents/skills"),
}
AGENTS = tuple(_SKILL_ROOTS)


def _read(*parts: str) -> str:
    return files(__package__).joinpath(*parts).read_text(encoding="utf-8")


def instructions() -> str:
    return _read("instructions.md").strip()


def skill() -> str:
    return _read(SKILL_NAME, "SKILL.md")


def snippet() -> str:
    return _read("AGENTS.snippet.md")


def skill_path(
    agent: str, scope: str = "project", project_root: Path | None = None
) -> Path:
    project_rel, home_rel = _SKILL_ROOTS[agent]
    base = (
        Path.home() / home_rel
        if scope == "global"
        else (project_root or Path.cwd()) / project_rel
    )
    return base / SKILL_NAME / "SKILL.md"


def install_skill(
    agent: str = "opencode", scope: str = "project", project_root: Path | None = None
) -> Path:
    path = skill_path(agent, scope, project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(skill(), encoding="utf-8")
    return path
