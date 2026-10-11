"""Argparse composition root for the ember_aws operator CLI.

Run with: ``PYTHONPATH=deployment/aws uv run python -m ember_aws <cmd>``

Exit codes:
- 0: success (including "nothing to do")
- 1: preflight or validation failure, before any change
- 2: AWS or Tailscale operation failed
- 3: guarded deletion refused
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ._cli_parsers import (
    add_cache,
    add_deploy,
    add_destroy,
    add_logs,
    add_preflight,
    add_replace,
    add_rotate_token,
    add_ssh,
    add_start,
    add_status,
    add_stop,
    add_token,
    add_verify,
)
from .aws_clients import AwsClients
from .lifecycle import Lifecycle
from .lifecycle_control import LifecycleControl
from .model_cache import ModelCache
from .names import DeploymentName
from .preflight import Preflight
from .remote import Remote
from .sizing_table import SizingTable
from .status_reader import StatusReader
from .tailscale_client import TailscaleClient, TailscaleError

#: Path to sizing.json relative to this file.
_SIZING_JSON_PATH: Path = Path(__file__).parent.parent / "sizing.json"

#: A factory callable — ``(clients, tailscale, name=None)`` — that returns
#: (LifecycleControl, StatusReader, Remote, Lifecycle, ModelCache).
FactoryCallable = Callable[..., tuple[Any, Any, Any, Any, Any]]


def _make_clients(region: str) -> AwsClients:
    """Build real AWS clients for the given region.

    Parameters
    ----------
    region : str
        AWS region name.

    Returns
    -------
    AwsClients
        A frozen bundle of service clients.
    """
    return AwsClients.from_region(region)


def _make_tailscale() -> TailscaleClient | None:
    """Build a Tailscale client from environment variables, or None.

    Returns
    -------
    TailscaleClient | None
        A configured client, or ``None`` when the OAuth env vars are absent.
    """
    try:
        return TailscaleClient.from_env()
    except TailscaleError:
        return None


def _default_factory(
    clients: Any, tailscale: Any, name: str | None = None
) -> tuple[Any, Any, Any, Any, Any]:
    """Build the real control objects for all subcommands.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance.
    tailscale : Any
        A :class:`~ember_aws.tailscale_client.TailscaleClient` or ``None``.
    name : str | None
        Deployment name for the :class:`~ember_aws.remote.Remote`; ``None``
        (commands that do not use it) falls back to ``"default"``.

    Returns
    -------
    tuple[Any, Any, Any, Any, Any]
        ``(lifecycle_control, status_reader, remote, lifecycle, model_cache)``
    """
    mc = ModelCache(clients=clients)
    pf = Preflight(clients=clients, tailscale=tailscale)
    lc = Lifecycle(clients=clients, tailscale=tailscale, model_cache=mc, preflight=pf)
    lcc = LifecycleControl(clients=clients, tailscale=tailscale)
    sizing = SizingTable.load(_SIZING_JSON_PATH)
    sr = StatusReader(clients=clients, tailscale=tailscale, sizing=sizing)
    remote = Remote(names=DeploymentName(name=name or "default"))
    return lcc, sr, remote, lc, mc


def build(argv: list[str], factory: FactoryCallable | None = None) -> int:
    """Parse ``argv`` and dispatch to the appropriate handler.

    Parameters
    ----------
    argv : list[str]
        Command-line arguments (without the program name).
    factory : FactoryCallable | None
        Optional factory for injecting fakes in tests.  Defaults to
        :func:`_default_factory`.

    Returns
    -------
    int
        Exit code (0, 1, 2, or 3).
    """
    if factory is None:
        factory = _default_factory

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    result: int = args.handler(args, factory)
    return result


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns
    -------
    argparse.ArgumentParser
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="python -m ember_aws",
        description="Operator tooling for ember AWS GPU deployments.",
    )
    sub = parser.add_subparsers(dest="command")

    add_preflight(sub)
    add_cache(sub)
    add_deploy(sub)
    add_token(sub)
    add_status(sub)
    add_stop(sub)
    add_start(sub)
    add_logs(sub)
    add_ssh(sub)
    add_rotate_token(sub)
    add_destroy(sub)
    add_replace(sub)
    add_verify(sub)

    return parser


def main() -> int:
    """CLI entry point.

    Returns
    -------
    int
        Exit code.
    """
    return build(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
