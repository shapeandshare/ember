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
    return Path.home() / ".config" / "opencode" / "opencode.json"


def project_config_path(root: Path) -> Path:
    return root / "opencode.json"


def mcp_command() -> list[str]:
    """Prefer the installed console script; fall back to this interpreter + module."""
    exe = shutil.which("ember-mcp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "ember.mcp_server"]


def build_entry(host: str, port: int, autostart: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "local",
        "command": mcp_command(),
        "enabled": True,
        "timeout": 30000,
        "environment": {
            "EMBER_SERVER_URL": f"http://{host}:{port}",
            "EMBER_AUTOSTART": autostart,
        },
    }
    # Absolute command paths already avoid PATH issues, but opencode may be
    # launched with a stripped GUI PATH; set it explicitly as belt-and-suspenders.
    if os.environ.get("PATH"):
        entry["environment"]["PATH"] = os.environ["PATH"]
    return entry


def write(path: Path, host: str, port: int, autostart: str) -> Path:
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError:
            existing = {}
    existing.setdefault("$schema", SCHEMA)
    mcp = existing.setdefault("mcp", {})
    mcp["ember"] = build_entry(host, port, autostart)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2) + "\n")
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
    path.write_text(json.dumps(existing, indent=2) + "\n")
    return True
