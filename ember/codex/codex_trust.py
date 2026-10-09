"""Codex CLI project trust: whether Codex loads a project's ``.codex/config.toml``.

Codex loads project-scoped config only for a trusted project, so a project-scope
``ember init --codex`` can be silently ignored. ``trust_level`` reproduces Codex's own
lookup (``ProjectTrustLookup`` in ``codex-rs/config``): the candidate keys are the
working directory, then its main checkout root (a linked worktree maps to its
repository), each tried canonical first and then as spelled. The first key present
in the global ``[projects]`` table decides, even an entry without a
``trust_level``, and matching is by exact key, never by path prefix.
"""

from __future__ import annotations

import tomllib
from enum import StrEnum
from pathlib import Path

from ..cfg.repo_root import main_checkout_root
from .codex_config import global_config_path


class CodexTrust(StrEnum):
    """A ``projects.<path>.trust_level`` value in Codex's global config."""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


def trust_level(root: Path) -> CodexTrust | None:
    """Return Codex's trust decision for a session started in ``root``.

    Parameters
    ----------
    root : Path
        The directory Codex would be launched from.

    Returns
    -------
    CodexTrust | None
        The decided level, or ``None`` when Codex has no decision yet (it asks
        on first launch) or the global config is missing, malformed, or holds
        an unknown value.
    """
    try:
        config = tomllib.loads(global_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    projects = config.get("projects")
    if not isinstance(projects, dict):
        return None
    for key in _lookup_keys(root):
        if key in projects:
            entry = projects[key]
            level = entry.get("trust_level") if isinstance(entry, dict) else None
            if not isinstance(level, str):
                return None
            try:
                return CodexTrust(level)
            except ValueError:
                return None
    return None


def _lookup_keys(root: Path) -> list[str]:
    """Return Codex's ordered trust-lookup keys for ``root``.

    Parameters
    ----------
    root : Path
        The directory Codex would be launched from.

    Returns
    -------
    list[str]
        ``root`` then its main checkout root, each canonical first and then as
        spelled, without duplicates.
    """
    candidates = [root]
    repo = main_checkout_root(root)
    if repo is not None:
        candidates.append(repo)
    keys: list[str] = []
    for path in candidates:
        for key in (str(path.resolve()), str(path)):
            if key not in keys:
                keys.append(key)
    return keys
