"""Claude Code integration: detect where the ``ember`` MCP server is registered.

ember does not write Claude Code's config (users register with ``claude mcp add``),
but ``ember doctor`` reports where that registration lives. Claude Code keeps user-
and local-scope servers in ``~/.claude.json`` (``$CLAUDE_CONFIG_DIR/.claude.json``
when set): top-level ``mcpServers`` for user scope, and
``projects["<repository root>"].mcpServers`` for local scope. Project scope is
``.mcp.json`` at the repository root. Claude Code's own project-key
canonicalization varies across symlinks and worktrees, so the local-scope lookup
tries every plausible spelling of the root.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..cfg.repo_root import checkout_root, main_checkout_root

_SERVER_KEY = "ember"


def user_config_path() -> Path:
    """Return the file holding Claude Code's user- and local-scope MCP servers.

    Returns
    -------
    Path
        ``$CLAUDE_CONFIG_DIR/.claude.json`` when ``CLAUDE_CONFIG_DIR`` is set and
        non-empty, else ``~/.claude.json``.
    """
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "")
    return (Path(config_dir) if config_dir else Path.home()) / ".claude.json"


def project_config_path(start: Path) -> Path:
    """Return the project-scope ``.mcp.json`` for the repository containing ``start``.

    Parameters
    ----------
    start : Path
        Directory to search from.

    Returns
    -------
    Path
        ``<repository root>/.mcp.json``, or ``<start>/.mcp.json`` outside a git
        checkout.
    """
    return (checkout_root(start) or start) / ".mcp.json"


def has_user_entry() -> bool:
    """Return whether ember is registered at user scope (every project).

    Returns
    -------
    bool
        ``True`` if the user config has a top-level ``mcpServers.ember``.
    """
    return _has_server(_read_json(user_config_path()))


def has_local_entry(start: Path) -> bool:
    """Return whether ember is registered at local scope for this project.

    Parameters
    ----------
    start : Path
        Directory to search from.

    Returns
    -------
    bool
        ``True`` if the user config has ``projects[<root>].mcpServers.ember`` for
        the working directory or its repository root, in any spelling.
    """
    projects = _read_json(user_config_path()).get("projects")
    if not isinstance(projects, dict):
        return False
    return any(_has_server(projects.get(key)) for key in _project_keys(start))


def has_project_entry(start: Path) -> bool:
    """Return whether the repository's ``.mcp.json`` registers ember.

    Parameters
    ----------
    start : Path
        Directory to search from.

    Returns
    -------
    bool
        ``True`` if ``.mcp.json`` at the repository root has ``mcpServers.ember``.
    """
    return _has_server(_read_json(project_config_path(start)))


def _project_keys(start: Path) -> list[str]:
    """Return every plausible ``projects`` key Claude Code may use for ``start``.

    Parameters
    ----------
    start : Path
        Directory to search from.

    Returns
    -------
    list[str]
        The checkout root, the main checkout root, and ``start`` itself, each as
        spelled and canonical, without duplicates.
    """
    keys: list[str] = []
    for path in (checkout_root(start), main_checkout_root(start), start):
        if path is None:
            continue
        for key in (str(path), str(path.resolve())):
            if key not in keys:
                keys.append(key)
    return keys


def _read_json(path: Path) -> dict[str, Any]:
    """Return ``path`` parsed as a JSON object, or ``{}``.

    Parameters
    ----------
    path : Path
        JSON file to read.

    Returns
    -------
    dict[str, Any]
        The parsed object; empty when the file is missing, unreadable, not JSON,
        or not a JSON object.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _has_server(scope: object) -> bool:
    """Return whether a parsed config object holds ``mcpServers.ember``.

    Parameters
    ----------
    scope : object
        A top-level config object or one ``projects[...]`` entry.

    Returns
    -------
    bool
        ``True`` if ``scope`` is a mapping whose ``mcpServers`` contains ember.
    """
    servers = scope.get("mcpServers") if isinstance(scope, dict) else None
    return isinstance(servers, dict) and _SERVER_KEY in servers
