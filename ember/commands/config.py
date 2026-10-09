"""Configuration subcommand handlers: config path, config show."""

from __future__ import annotations

import argparse
import json

from ..cfg import config, paths


def cmd_config_path(_: argparse.Namespace) -> int:
    """Print the config file path (``ember config path``).

    Parameters
    ----------
    _ : argparse.Namespace
        Parsed CLI arguments (unused).

    Returns
    -------
    int
        Always ``0``.
    """
    print(paths.config_path())
    return 0


def cmd_config_show(_: argparse.Namespace) -> int:
    """Print the effective config with secrets masked (``ember config show``).

    Every key is resolved through ``config.resolve()`` (flag > env > config
    file > default precedence), not just read from the config file, so an
    ``EMBER_*`` environment-variable override is always reflected — a
    config-file-only read would silently hide an active env var override
    (found during critical review, 2026-10-08).

    Parameters
    ----------
    _ : argparse.Namespace
        Parsed CLI arguments (unused).

    Returns
    -------
    int
        Always ``0``.
    """
    secret_keys = {
        "auth_token",
        "server_auth_token",
        "s3_access_key_id",
        "s3_secret_access_key",
    }
    effective = {
        key: (
            "***" if key in secret_keys and config.resolve(key) else config.resolve(key)
        )
        for key in config.DEFAULTS
    }
    print(json.dumps(effective, indent=2))
    return 0
