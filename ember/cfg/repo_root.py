"""Find a directory's git checkout root, mapping a linked worktree to its main repo.

Coding-agent harnesses key per-project state by repository root: Codex keys project
trust by the main checkout (a linked worktree resolves to the repository it belongs
to), and Claude Code keys local-scope MCP servers by the repository root. Both are
resolved here by reading ``.git`` on disk, never by running ``git``, so
``ember doctor`` stays fast and free of side effects.
"""

from __future__ import annotations

from pathlib import Path

_GITDIR_PREFIX = "gitdir:"


def checkout_root(start: Path) -> Path | None:
    """Return the nearest directory at or above ``start`` that contains ``.git``.

    Parameters
    ----------
    start : Path
        Directory to search from.

    Returns
    -------
    Path | None
        The checkout root, or ``None`` outside a git checkout.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def main_checkout_root(start: Path) -> Path | None:
    """Return the main checkout for ``start``, mapping a linked worktree to its repo.

    A linked worktree's ``.git`` is a file (``gitdir: <main>/.git/worktrees/<name>``)
    whose admin directory names the shared ``.git`` in ``commondir``; the main
    checkout is that directory's parent. A plain checkout, a submodule, or a
    separate git directory resolves to the checkout root itself.

    Parameters
    ----------
    start : Path
        Directory to search from.

    Returns
    -------
    Path | None
        The main checkout root, or ``None`` outside a git checkout.
    """
    root = checkout_root(start)
    if root is None or not (root / ".git").is_file():
        return root
    common = _common_dir(root)
    return common.parent if common is not None and common.name == ".git" else root


def _common_dir(root: Path) -> Path | None:
    """Return the shared ``.git`` that a worktree's ``.git`` file points at.

    Parameters
    ----------
    root : Path
        A checkout root whose ``.git`` is a file.

    Returns
    -------
    Path | None
        The resolved common git directory, or ``None`` when the pointer or its
        ``commondir`` is missing or unreadable (as for a submodule).
    """
    try:
        pointer = (root / ".git").read_text(encoding="utf-8").strip()
        if not pointer.startswith(_GITDIR_PREFIX):
            return None
        admin = (root / pointer.removeprefix(_GITDIR_PREFIX).strip()).resolve()
        common = (admin / "commondir").read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return (admin / common).resolve()
