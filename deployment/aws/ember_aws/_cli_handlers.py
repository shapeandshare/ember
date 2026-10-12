"""Command handlers for the ember_aws operator CLI.

Each ``_handle_*`` function corresponds to one argparse subcommand.
They are imported by ``__main__`` and wired to subcommand parsers there.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from .capacity import Capacity
from .deployment import Deployment
from .lifecycle import StackDeployError
from .model_cache import CacheInUseError, ConfirmationError
from .sizing_table import SizingError

#: Type alias for the dependency factory callable.
FactoryCallable = Any


def _make_clients_and_tailscale(
    region: str,
) -> tuple[Any, Any]:
    """Build real AWS clients and a Tailscale client.

    Parameters
    ----------
    region : str
        AWS region name.

    Returns
    -------
    tuple[Any, Any]
        ``(clients, tailscale)`` where ``tailscale`` may be ``None``.
    """
    from .aws_clients import AwsClients
    from .tailscale_client import TailscaleClient, TailscaleError

    clients = AwsClients.from_region(region)
    try:
        tailscale: Any = TailscaleClient.from_env()
    except TailscaleError:
        tailscale = None
    return clients, tailscale


def handle_preflight(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the preflight subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory.

    Returns
    -------
    int
        Exit code.
    """
    clients, tailscale = _make_clients_and_tailscale(args.region)
    _lcc, _sr, _remote, _lc, _mc = factory(clients, tailscale)
    pf = getattr(_lc, "_preflight", _lc)

    deployment = Deployment(
        name=args.name,
        model=args.model,
        region=args.region,
        instance_type=getattr(args, "instance_type", None),
    )

    results = pf.run(deployment)
    has_blocking_failure = False
    for r in results:
        if not r.ok:
            marker = "✗" if r.blocking else "!"
            print(f"{marker} {r.check.value}: {r.problem} — fix: {r.fix}")
            if r.blocking:
                has_blocking_failure = True

    return 1 if has_blocking_failure else 0


def handle_cache_dispatch(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Dispatch to the correct cache sub-handler.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory.

    Returns
    -------
    int
        Exit code.
    """
    if not hasattr(args, "handler") or args.handler is handle_cache_dispatch:
        print("Usage: ember_aws cache {add,list,rm,destroy}", file=sys.stderr)
        return 1
    result: int = args.handler(args, factory)
    return result


def handle_cache_add(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle cache add.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory.

    Returns
    -------
    int
        Exit code.
    """
    clients, tailscale = _make_clients_and_tailscale(args.region)
    _lcc, _sr, _remote, _lc, mc = factory(clients, tailscale)

    try:
        mc.add(
            args.model,
            bucket=getattr(args, "bucket", None),
            prefix=getattr(args, "prefix", "models/"),
        )
        return 0
    except CacheInUseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_cache_list(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle cache list.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory.

    Returns
    -------
    int
        Exit code.
    """
    clients, tailscale = _make_clients_and_tailscale(args.region)
    _lcc, _sr, _remote, _lc, mc = factory(clients, tailscale)

    try:
        items = mc.list(
            bucket=getattr(args, "bucket", None),
            prefix=getattr(args, "prefix", "models/"),
        )
        for item in items:
            rev = item.get("revision", "?")
            status = item.get("status", "?")
            line = f"{item['model']}@{rev} ({status})"
            total_bytes = item.get("total_bytes")
            if total_bytes:
                line += f" {total_bytes / 2**30:.1f} GiB"
            deployments = item.get("deployments") or []
            if deployments:
                line += f" - used by: {', '.join(deployments)}"
            print(line)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_cache_rm(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle cache rm.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory.

    Returns
    -------
    int
        Exit code.
    """
    clients, tailscale = _make_clients_and_tailscale(args.region)
    _lcc, _sr, _remote, _lc, mc = factory(clients, tailscale)

    revision = getattr(args, "revision", None)
    if revision is None:
        import ember.models as ember_models  # import-placement:allow

        spec = ember_models.REGISTRY.get(args.model)
        revision = (spec.revision or "latest") if spec is not None else None
        if revision is None:
            print(
                f"error: no pinned revision for model {args.model!r}; pass --revision",
                file=sys.stderr,
            )
            return 1

    try:
        mc.remove(
            args.model,
            revision,
            bucket=getattr(args, "bucket", None),
            prefix=getattr(args, "prefix", "models/"),
        )
        return 0
    except CacheInUseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_cache_destroy(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle cache destroy.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory.

    Returns
    -------
    int
        Exit code.
    """
    clients, tailscale = _make_clients_and_tailscale(args.region)
    _lcc, _sr, _remote, _lc, mc = factory(clients, tailscale)

    try:
        mc.destroy(
            args.confirm,
            bucket=getattr(args, "bucket", None),
        )
        return 0
    except (CacheInUseError, ConfirmationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_deploy(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the deploy subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory.

    Returns
    -------
    int
        Exit code.
    """
    clients, tailscale = _make_clients_and_tailscale(args.region)
    _lcc, _sr, _remote, lc, _mc = factory(clients, tailscale)

    kwargs: dict[str, Any] = {
        "name": args.name,
        "model": args.model,
        "region": args.region,
        "capacity": Capacity(args.capacity),
        "idle_minutes": args.idle_minutes,
    }
    if getattr(args, "instance_type", None):
        kwargs["instance_type"] = args.instance_type
    if getattr(args, "ember_version", ""):
        kwargs["ember_version"] = args.ember_version

    deployment = Deployment(**kwargs)

    try:
        lc.deploy(deployment)
        return 0
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1
    except SizingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except StackDeployError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_token(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the token subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory.

    Returns
    -------
    int
        Exit code.
    """
    clients, tailscale = _make_clients_and_tailscale(args.region)
    _lcc, _sr, _remote, lc, _mc = factory(clients, tailscale)

    deployment = Deployment(name=args.name, model=args.model, region=args.region)

    try:
        lc.token(deployment)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
