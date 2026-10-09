"""Per-harness report of where the ``ember`` MCP server is registered.

``ember doctor`` prints it so a user can see, in one place, whether opencode, Kilo
Code, Codex CLI, and Claude Code will load ember in this directory and globally. It
only reads each harness's own config files and never runs a harness CLI, and it
flags registrations a harness will ignore (an untrusted Codex project) or that still
need approval (a Claude Code ``.mcp.json``).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..claude import claude_config
from ..codex import codex_config
from ..codex.codex_trust import CodexTrust, trust_level
from ..kilocode import kilocode_config
from ..opencode import opencode_config, opencode_plugin

_EVERY_REPO = "(add --global for every repo)"


def codex_trust_note(root: Path) -> str | None:
    """Return why Codex would ignore ``root``'s ``.codex/config.toml``, if it would.

    Parameters
    ----------
    root : Path
        The project directory.

    Returns
    -------
    str | None
        ``None`` for a trusted project, otherwise an actionable reason.
    """
    level = trust_level(root)
    if level is CodexTrust.TRUSTED:
        return None
    if level is CodexTrust.UNTRUSTED:
        return f"ignored: marked untrusted in {codex_config.global_config_path()}"
    return (
        "ignored until you trust this project at Codex's first-launch prompt, "
        "or run `ember init --codex --global`"
    )


def registration_lines(root: Path) -> list[tuple[str, str]]:
    """Return ``(label, detail)`` doctor lines for every supported harness.

    Parameters
    ----------
    root : Path
        The directory doctor runs in; project-scope configs are looked up here.

    Returns
    -------
    list[tuple[str, str]]
        For each harness, its binary on ``PATH`` and where ember is registered
        (or the command that registers it), plus an ``opencode legacy`` line
        when the global opencode config still holds the ``mcp.vault`` entry
        that older ``ember init`` versions added.
    """
    harnesses = (
        ("opencode", _opencode(root), f"run `ember init --opencode` {_EVERY_REPO}"),
        ("kilo", _kilo(root), f"run `ember init --kilocode` {_EVERY_REPO}"),
        ("codex", _codex(root), f"run `ember init --codex` {_EVERY_REPO}"),
        (
            "claude",
            _claude(root),
            "run `claude mcp add --scope user ember -- ember-mcp`, or install the "
            "plugin: `claude plugin marketplace add shapeandshare/ember` then "
            f"`claude plugin install {claude_config.PLUGIN_ID}`",
        ),
    )
    lines: list[tuple[str, str]] = []
    for name, found, next_step in harnesses:
        lines.append((name, shutil.which(name) or "not on PATH"))
        lines.append(
            (f"{name} registration", "; ".join(found) or f"none — {next_step}")
        )
    legacy = opencode_config.global_config_path()
    if opencode_config.has_legacy_vault_entry(legacy):
        lines.append(
            (
                "opencode legacy",
                f"{legacy} still has the mcp.vault entry older `ember init` versions "
                "added; remove it unless you use the vault MCP server",
            )
        )
    return lines


def _opencode(root: Path) -> list[str]:
    """Return where opencode registers ember: config entries and plugin files.

    Parameters
    ----------
    root : Path
        The project directory.

    Returns
    -------
    list[str]
        One description per registration found, project scope first.
    """
    found: list[str] = []
    for scope, config in (
        ("project", opencode_config.project_config_path(root)),
        ("global", opencode_config.global_config_path()),
    ):
        if opencode_config.has_entry(config):
            found.append(f"{scope} config {config}")
        plugin = (
            opencode_plugin.plugin_dir(scope, root) / opencode_plugin.PLUGIN_FILENAME
        )
        if plugin.exists():
            found.append(f"{scope} plugin {plugin}")
    return found


def _kilo(root: Path) -> list[str]:
    """Return where Kilo Code registers ember.

    Parameters
    ----------
    root : Path
        The project directory.

    Returns
    -------
    list[str]
        One description per registration found, project scope first.
    """
    return [
        f"{scope} {config}"
        for scope, config in (
            ("project", kilocode_config.project_config_path(root)),
            ("global", kilocode_config.global_config_path()),
        )
        if kilocode_config.has_entry(config)
    ]


def _codex(root: Path) -> list[str]:
    """Return where Codex CLI registers ember, flagging an ignored project file.

    Parameters
    ----------
    root : Path
        The project directory.

    Returns
    -------
    list[str]
        One description per registration found, project scope first.
    """
    found: list[str] = []
    project = codex_config.project_config_path(root)
    if codex_config.has_entry(project):
        note = codex_trust_note(root)
        found.append(f"project {project} ({note})" if note else f"project {project}")
    config = codex_config.global_config_path()
    if codex_config.has_entry(config):
        found.append(f"global {config}")
    return found


def _claude(root: Path) -> list[str]:
    """Return where Claude Code registers ember: ``claude mcp add`` scopes, plugin.

    Parameters
    ----------
    root : Path
        The project directory.

    Returns
    -------
    list[str]
        One description per scope found: user, local, project, then the plugin.
    """
    found: list[str] = []
    user = claude_config.user_config_path()
    if claude_config.has_user_entry():
        found.append(f"user {user}")
    if claude_config.has_local_entry(root):
        found.append(f"local {user} (this project)")
    if claude_config.has_project_entry(root):
        found.append(
            f"project {claude_config.project_config_path(root)} (approve it when "
            "Claude Code asks; `claude mcp list` shows the state)"
        )
    scopes = claude_config.plugin_scopes(root)
    if scopes:
        where = ", ".join(f"{scope} {path}" for scope, path in scopes)
        found.append(f"plugin {claude_config.PLUGIN_ID} ({where})")
    return found
