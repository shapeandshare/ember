"""Public API for the ember agent onboarding kit.

Exposes constants and helpers for reading and installing the kit artifacts:
MCP ``initialize.instructions``, the ``ember://guide`` skill, the AGENTS.md
snippet, and skill installation paths.
"""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path

SKILL_NAME = "ember-advise"
GUIDE_URI = "ember://guide"

_SKILL_ROOTS: dict[str, tuple[str, str]] = {
    "opencode": (".opencode/skills", ".config/opencode/skills"),
    "claude": (".claude/skills", ".claude/skills"),
    "codex": (".agents/skills", ".agents/skills"),
    "kilocode": (".kilo/skills", ".config/kilo/skills"),
}
AGENTS = tuple(_SKILL_ROOTS)


def _read(*parts: str) -> str:
    return files("ember.agent_kit").joinpath(*parts).read_text(encoding="utf-8")


def instructions() -> str:
    """Return the MCP ``initialize.instructions`` text.

    Returns
    -------
    str
        The contents of ``instructions.md``, stripped of surrounding
        whitespace.
    """
    return _read("instructions.md").strip()


def skill() -> str:
    """Return the ``ember-advise`` skill's ``SKILL.md`` content.

    Returns
    -------
    str
        The full playbook served as ``ember://guide`` and installed as a skill.
    """
    return _read(SKILL_NAME, "SKILL.md")


def snippet() -> str:
    """Return the AGENTS.md / CLAUDE.md policy snippet.

    Returns
    -------
    str
        The contents of ``AGENTS.snippet.md``.
    """
    return _read("AGENTS.snippet.md")


def skill_path(
    agent: str, scope: str = "project", project_root: Path | None = None
) -> Path:
    """Return where the ``ember-advise`` skill would be installed for an agent.

    Parameters
    ----------
    agent : str
        One of the keys in ``_SKILL_ROOTS`` (``"opencode"``, ``"claude"``,
        ``"codex"``, ``"kilocode"``).
    scope : str, optional
        ``"project"`` (default) for a project-local install, or ``"global"``
        for the user's home directory.
    project_root : Path | None, optional
        Root to install under when ``scope`` is ``"project"``; defaults to
        the current working directory.

    Returns
    -------
    Path
        The ``SKILL.md`` path for the given agent and scope.
    """
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
    """Write the ``ember-advise`` skill to disk for an agent.

    Parameters
    ----------
    agent : str, optional
        One of the keys in ``_SKILL_ROOTS``. Defaults to ``"opencode"``.
    scope : str, optional
        ``"project"`` (default) or ``"global"``.
    project_root : Path | None, optional
        Root to install under when ``scope`` is ``"project"``; defaults to
        the current working directory.

    Returns
    -------
    Path
        The ``SKILL.md`` path written to.
    """
    path = skill_path(agent, scope, project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(skill(), encoding="utf-8")
    os.replace(tmp, path)
    return path
