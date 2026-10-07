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

    Parameters
    ----------
    _ : argparse.Namespace
        Parsed CLI arguments (unused).

    Returns
    -------
    int
        Always ``0``.
    """
    effective = dict(config.load())
    effective["server_url"] = config.resolve("server_url")
    for key in ("auth_token", "server_auth_token"):
        effective[key] = "***" if config.resolve(key) else None
    print(json.dumps(effective, indent=2))
    return 0
