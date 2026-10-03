"""Platform-aware locations for config, state, logs, and the model cache.

macOS: ``~/Library/Application Support/clef-local`` (config + state).
Other: XDG (``$XDG_CONFIG_HOME`` / ``$XDG_STATE_HOME``).

Model weights are left in HuggingFace's own cache so they are shared with any
other HF-based tool the user already has (avoids re-downloading ~18 GB).
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

APP_NAME = "clef-local"


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def config_dir() -> Path:
    if sys.platform == "darwin":
        path = _support_dir()
    else:
        path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_dir() -> Path:
    if sys.platform == "darwin":
        path = _support_dir()
    else:
        path = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = state_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def state_path() -> Path:
    return state_dir() / "state.json"


def pid_path() -> Path:
    return state_dir() / "server.pid"


def server_log_path() -> Path:
    return log_dir() / "server.log"


def hf_hub_cache() -> Path:
    """Where huggingface_hub stores snapshots (its own default, unless overridden)."""
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    base = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return Path(base) / "huggingface" / "hub"
