"""Platform-aware locations for config, state, logs, and the model cache.

macOS keeps config and state in ``~/Library/Application Support/ember``; other
platforms use XDG directories. ``EMBER_STATE_DIR`` relocates state (pid file and
logs), which keeps tests and side-by-side instances isolated. Model weights stay in
Hugging Face's own cache so they are shared with other HF-based tools.
"""

from __future__ import annotations

import hashlib
import os
import platform
import sys
from pathlib import Path

APP_NAME = "ember"


def is_apple_silicon() -> bool:
    """Return whether this process is running on Apple Silicon macOS.

    Returns
    -------
    bool
        ``True`` on macOS with an ``arm64`` machine type, ``False`` otherwise.
    """
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _support_dir() -> Path:
    """Return the macOS Application Support directory for ember.

    Returns
    -------
    Path
        ``~/Library/Application Support/ember``.
    """
    return Path.home() / "Library" / "Application Support" / APP_NAME


def config_dir() -> Path:
    """Return the platform's config directory, creating it if needed.

    Returns
    -------
    Path
        macOS: ``~/Library/Application Support/ember``. Other platforms:
        ``$XDG_CONFIG_HOME/ember`` (default ``~/.config/ember``).
    """
    if sys.platform == "darwin":
        path = _support_dir()
    else:
        path = (
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
        )
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_dir() -> Path:
    """Return the platform's state directory, creating it if needed.

    ``EMBER_STATE_DIR`` overrides the default location, which keeps tests and
    side-by-side instances isolated.

    Returns
    -------
    Path
        ``EMBER_STATE_DIR`` if set; otherwise macOS's Application Support
        directory, or ``$XDG_STATE_HOME/ember`` on other platforms.
    """
    override = os.environ.get("EMBER_STATE_DIR")
    if override:
        path = Path(override)
    elif sys.platform == "darwin":
        path = _support_dir()
    else:
        path = (
            Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
            / APP_NAME
        )
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    """Return the ``logs`` subdirectory of the state directory, creating it.

    Returns
    -------
    Path
        ``<state_dir>/logs``.
    """
    path = state_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    """Return the path to the JSON config file.

    Returns
    -------
    Path
        ``<config_dir>/config.json``.
    """
    return config_dir() / "config.json"


def pid_path() -> Path:
    """Return the path to the model server's pid file.

    Returns
    -------
    Path
        ``<state_dir>/server.pid``.
    """
    return state_dir() / "server.pid"


def server_log_path() -> Path:
    """Return the path to the model server's log file.

    Returns
    -------
    Path
        ``<log_dir>/server.log``.
    """
    return log_dir() / "server.log"


def hf_hub_cache() -> Path:
    """Return the Hugging Face Hub cache directory used for model weights.

    Checks ``HF_HUB_CACHE`` and ``HF_HOME`` before falling back to the
    standard ``huggingface/hub`` path under the XDG cache home.

    Returns
    -------
    Path
        The resolved Hugging Face Hub cache directory.
    """
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    base = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return Path(base) / "huggingface" / "hub"


def hosted_model_cache(uri: str) -> Path:
    """Return the local cache directory for an ``EMBER_MODEL_S3_URI`` download.

    A hosting platform (e.g. Outerbounds) supplies the model's S3 location as
    a URI at start time, with no ``REGISTRY`` entry and therefore no stable
    ``dir_name`` to key a cache directory by. The URI itself is hashed
    (SHA-256, truncated) into a short, filesystem-safe, deterministic
    directory name instead, so the same URI always resolves to the same
    local path and re-running ``ember start`` against an unchanged URI does
    not re-download.

    Unlike ``config_dir()``/``state_dir()``/``log_dir()`` (needed by every
    ember invocation and safe to create eagerly), this directory is relevant
    only when ``EMBER_MODEL_S3_URI`` is configured. It is therefore a pure
    path computation, like ``hf_hub_cache()`` — the caller
    (``ember.serving.hosted.resolve()``) is responsible for creating it.

    Parameters
    ----------
    uri : str
        The full ``s3://bucket/prefix`` URI.

    Returns
    -------
    Path
        ``<XDG cache home>/ember/hosted-models/<sha256-prefix-of-uri>``. Not
        created as a side effect of calling this function.
    """
    digest = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:16]
    base = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return Path(base) / APP_NAME / "hosted-models" / digest
