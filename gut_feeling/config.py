"""JSON config with env-var and CLI-flag precedence.

Precedence (highest first): CLI flag > GUT_FEELING_* env var > config file > default.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "model": "flash",
    "host": "127.0.0.1",
    "port": 8765,
    "device": "auto",
    "max_length": 16384,
}


def load() -> dict[str, Any]:
    config = dict(DEFAULTS)
    path = paths.config_path()
    if path.exists():
        try:
            config.update(json.loads(path.read_text()))
        except json.JSONDecodeError:
            pass
    return config


def save(config: dict[str, Any]) -> Path:
    path = paths.config_path()
    path.write_text(json.dumps(config, indent=2) + "\n")
    return path


def resolve(key: str, flag: Any = None, env: str | None = None) -> Any:
    """Resolve a setting with flag > env > config > default precedence."""
    if flag is not None:
        return flag
    env_name = env or f"GUT_FEELING_{key.upper()}"
    if os.environ.get(env_name) not in (None, ""):
        value: Any = os.environ[env_name]
        default = DEFAULTS.get(key)
        if isinstance(default, bool):
            return value.lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return default
        return value
    return load().get(key, DEFAULTS.get(key))
