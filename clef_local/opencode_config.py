"""OpenCode integration: build and merge the `mcp.clef` config entry."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

SCHEMA = "https://opencode.ai/config.json"


def global_config_path() -> Path:
    return Path.home() / ".config" / "opencode" / "opencode.json"


def project_config_path(root: Path) -> Path:
    return root / "opencode.json"


def mcp_command() -> list[str]:
    """Prefer the installed console script; fall back to this interpreter + module."""
    exe = shutil.which("clef-mcp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "clef_local.mcp_server"]


def build_entry(host: str, port: int, autostart: str) -> dict:
    entry: dict = {
        "type": "local",
        "command": mcp_command(),
        "enabled": True,
        "timeout": 30000,
        "environment": {
            "CLEF_SERVER_URL": f"http://{host}:{port}",
            "CLEF_AUTOSTART": autostart,
        },
    }
    # Absolute command paths already avoid PATH issues, but opencode may be
    # launched with a stripped GUI PATH; set it explicitly as belt-and-suspenders.
    if os.environ.get("PATH"):
        entry["environment"]["PATH"] = os.environ["PATH"]
    return entry


def write(path: Path, host: str, port: int, autostart: str) -> Path:
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError:
            existing = {}
    existing.setdefault("$schema", SCHEMA)
    mcp = existing.setdefault("mcp", {})
    mcp["clef"] = build_entry(host, port, autostart)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2) + "\n")
    return path
