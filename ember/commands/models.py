"""Model lifecycle subcommand handlers: model pull, list, path, rm."""

from __future__ import annotations

import argparse
import json

from .. import models as models_mod


def cmd_model_pull(args: argparse.Namespace) -> int:
    """Download a model's pinned weights (``ember model pull``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.name`` and ``args.allow_low_disk``.

    Returns
    -------
    int
        Always ``0``.
    """
    path = models_mod.pull(args.name, allow_low_disk=args.allow_low_disk)
    print(f"{args.name or models_mod.DEFAULT} ready at {path}")
    return 0


def cmd_model_list(_: argparse.Namespace) -> int:
    """List models and where they are cached (``ember model list``).

    Parameters
    ----------
    _ : argparse.Namespace
        Parsed CLI arguments (unused).

    Returns
    -------
    int
        Always ``0``.
    """
    print(json.dumps(models_mod.list_models(), indent=2))
    return 0


def cmd_model_path(args: argparse.Namespace) -> int:
    """Print the directory a model runs from (``ember model path``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.name``.

    Returns
    -------
    int
        ``0`` if the model is pulled, ``1`` otherwise.
    """
    resolved = models_mod.resolve_dir(args.name)
    if resolved is None:
        print("not pulled")
        return 1
    print(resolved)
    return 0


def cmd_model_rm(args: argparse.Namespace) -> int:
    """Delete a model's local files (``ember model rm``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.name`` and ``args.yes``.

    Returns
    -------
    int
        ``0`` if removed; ``1`` if the confirmation prompt was declined.
    """
    if not args.yes:
        answer = (
            input(f"Remove model {args.name or models_mod.DEFAULT}? [y/N] ")
            .strip()
            .lower()
        )
        if answer != "y":
            print("aborted")
            return 1
    print(models_mod.remove(args.name))
    return 0
