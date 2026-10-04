"""OpenCode integration: write, merge, and remove the `mcp.ember` config entry."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

SCHEMA = "https://opencode.ai/config.json"


def global_config_path() -> Path:
    """Return the user-global opencode config path.

    Returns
    -------
    Path
        ``~/.config/opencode/opencode.json``.
    """
    return Path.home() / ".config" / "opencode" / "opencode.json"


def project_config_path(root: Path) -> Path:
    """Return the project-local opencode config path.

    Parameters
    ----------
    root : Path
        Project root directory.

    Returns
    -------
    Path
        ``<root>/opencode.json``.
    """
    return root / "opencode.json"


def mcp_command() -> list[str]:
    """Prefer the installed console script; fall back to this interpreter + module."""
    exe = shutil.which("ember-mcp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "ember.mcp.mcp_server"]


VAULT_MCP_PACKAGE = "@bitbonsai/mcpvault@0.12.4"


def build_vault_entry() -> dict[str, Any]:
    """Build the ``mcp.vault`` entry for a project-local opencode config file.

    Returns
    -------
    dict[str, Any]
        The ``mcp.vault`` entry pointing at the ``vault/`` subdirectory.
    """
    return {
        "type": "local",
        "command": ["npx", "-y", VAULT_MCP_PACKAGE, "vault"],
        "enabled": True,
    }


def build_entry(host: str, port: int, autostart: str) -> dict[str, Any]:
    """Build the ``mcp.ember`` entry for an opencode config file.

    Parameters
    ----------
    host : str
        Model server host for ``EMBER_SERVER_URL``.
    port : int
        Model server port for ``EMBER_SERVER_URL``.
    autostart : str
        Value for ``EMBER_AUTOSTART`` (``"1"`` or ``"0"``).

    Returns
    -------
    dict[str, Any]
        The ``mcp.ember`` entry.
    """
    return {
        "type": "local",
        "command": mcp_command(),
        "enabled": True,
        "timeout": 30000,
        "environment": {
            "EMBER_SERVER_URL": f"http://{host}:{port}",
            "EMBER_AUTOSTART": autostart,
        },
    }


def write(path: Path, host: str, port: int, autostart: str) -> Path:
    """Merge the ``mcp.ember`` entry into an opencode config file.

    Preserves any other existing keys in ``path``; creates the file and its
    parent directories if they do not exist.

    Parameters
    ----------
    path : Path
        Config file to read and overwrite.
    host : str
        Model server host for ``EMBER_SERVER_URL``.
    port : int
        Model server port for ``EMBER_SERVER_URL``.
    autostart : str
        Value for ``EMBER_AUTOSTART`` (``"1"`` or ``"0"``).

    Returns
    -------
    Path
        ``path``, after writing.
    """
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError:
            existing = {}
    existing.setdefault("$schema", SCHEMA)
    mcp = existing.setdefault("mcp", {})
    mcp.setdefault("vault", build_vault_entry())
    mcp["ember"] = build_entry(host, port, autostart)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def remove(path: Path) -> bool:
    """Drop the `mcp.ember` entry; False if it is absent or not plain JSON."""
    try:
        existing = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    if "ember" not in existing.get("mcp", {}):
        return False
    del existing["mcp"]["ember"]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return True
