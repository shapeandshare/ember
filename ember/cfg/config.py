"""JSON config with env-var and CLI-flag precedence.

Precedence (highest first): CLI flag > EMBER_* env var > config file > default.
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
    # 0 means "the model's own maximum" (ember.serving.runtime.model_max_length).
    "max_length": 0,
    # 0 means no per-request cap; positive values cap tokenized input before inference.
    # Default 32768 guards against accidental MPS OOM from oversized single requests
    # (D-002). Set EMBER_MAX_REQUEST_LENGTH=0 to restore the model-maximum behaviour.
    "max_request_length": 32768,
}


def load() -> dict[str, Any]:
    """Load the config file, merged over the defaults.

    Returns
    -------
    dict[str, Any]
        ``DEFAULTS`` overridden by any keys present in the config file. A
        malformed config file is ignored and the defaults are returned as-is.
    """
    config = dict(DEFAULTS)
    path = paths.config_path()
    if path.exists():
        try:
            config.update(json.loads(path.read_text()))
        except json.JSONDecodeError:
            pass
    return config


def save(config: dict[str, Any]) -> Path:
    """Write a config dict to the config file as JSON.

    Parameters
    ----------
    config : dict[str, Any]
        The full config to persist.

    Returns
    -------
    Path
        The config file path written to.
    """
    path = paths.config_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def resolve(key: str, flag: Any = None, env: str | None = None) -> Any:
    """Resolve a setting with flag > env > config > default precedence."""
    if flag is not None:
        return flag
    env_name = env or f"EMBER_{key.upper()}"
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
