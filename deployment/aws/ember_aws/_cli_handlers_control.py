"""Command handlers for US2 control-plane subcommands.

Handles: status, stop, start, logs, ssh, rotate-token, destroy, verify.
Imported by ``__main__`` and wired to subcommand parsers there.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .defaults import DEFAULT_REGION
from .deployment import Deployment
from .names import DeploymentName

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
    from .aws_clients import AwsClients  # import-placement:allow
    from .tailscale_client import (
        TailscaleClient,
        TailscaleError,
    )  # import-placement:allow

    clients = AwsClients.from_region(region)
    try:
        tailscale: Any = TailscaleClient.from_env()
    except TailscaleError:
        tailscale = None
    return clients, tailscale


def _is_parameter_not_found(exc: Exception) -> bool:
    """Return whether an exception is SSM's ``ParameterNotFound`` error.

    Parameters
    ----------
    exc : Exception
        The exception caught from an SSM call.

    Returns
    -------
    bool
        ``True`` when ``exc`` is a boto3 ``ClientError`` whose code is
        ``ParameterNotFound``.
    """
    from botocore.exceptions import ClientError  # import-placement:allow

    if not isinstance(exc, ClientError):
        return False
    code = (exc.response.get("Error") or {}).get("Code", "")
    return code == "ParameterNotFound"


def handle_status(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the status subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory returning ``(lcc, sr, remote, lc, mc)``.

    Returns
    -------
    int
        Exit code.
    """
    region = getattr(args, "region", DEFAULT_REGION)
    clients, tailscale = _make_clients_and_tailscale(region)
    _lcc, sr, _remote, _lc, _mc = factory(clients, tailscale)

    names = DeploymentName(name=args.name)

    try:
        status = sr.read(names)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if getattr(args, "json", False):
        print(json.dumps(status.model_dump(mode="json")))
        return 0

    # Plain-text output: state plus optional fields.
    print(f"state: {status.state.value}")
    if status.instance_type:
        print(f"instance: {status.instance_type}")
    if status.capacity:
        print(f"capacity: {status.capacity}")
    if status.az:
        print(f"az: {status.az}")
    if status.url:
        print(f"url: {status.url}")
    if status.stop_reason:
        print(f"stop_reason: {status.stop_reason.value}")
    if status.idle_minutes is not None:
        print(f"idle_minutes: {status.idle_minutes}")
    if status.uptime is not None:
        print(f"uptime_s: {status.uptime:.0f}")
    if status.cost_since_start_usd is not None:
        print(f"cost_estimate_usd: {status.cost_since_start_usd:.2f}")
    if status.health:
        if "error" in status.health:
            print(f"health: error — {status.health['error']}")
        else:
            device = (status.health.get("engine") or {}).get("device", "?")
            print(f"health: ok (device={device})")
    return 0


def handle_stop(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the stop subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory returning ``(lcc, sr, remote, lc, mc)``.

    Returns
    -------
    int
        Exit code.
    """
    region = getattr(args, "region", DEFAULT_REGION)
    clients, tailscale = _make_clients_and_tailscale(region)
    lcc, _sr, _remote, _lc, _mc = factory(clients, tailscale)

    deployment = Deployment(name=args.name, model="flash", region=region)

    try:
        lcc.stop(deployment)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_start(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the start subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory returning ``(lcc, sr, remote, lc, mc)``.

    Returns
    -------
    int
        Exit code.
    """
    region = getattr(args, "region", DEFAULT_REGION)
    clients, tailscale = _make_clients_and_tailscale(region)
    lcc, _sr, _remote, _lc, _mc = factory(clients, tailscale)

    deployment = Deployment(name=args.name, model="flash", region=region)

    try:
        lcc.start(deployment)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_logs(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the logs subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory returning ``(lcc, sr, remote, lc, mc)``.

    Returns
    -------
    int
        Exit code.
    """
    clients, tailscale = _make_clients_and_tailscale(DEFAULT_REGION)
    _lcc, _sr, remote, _lc, _mc = factory(clients, tailscale)

    unit = getattr(args, "unit", "ember")
    follow = getattr(args, "follow", False)

    try:
        remote.logs(unit=unit, follow=follow)
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_ssh(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the ssh subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory returning ``(lcc, sr, remote, lc, mc)``.

    Returns
    -------
    int
        Exit code.
    """
    clients, tailscale = _make_clients_and_tailscale(DEFAULT_REGION)
    _lcc, _sr, remote, _lc, _mc = factory(clients, tailscale)

    try:
        remote.ssh()
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_rotate_token(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the rotate-token subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory returning ``(lcc, sr, remote, lc, mc)``.

    Returns
    -------
    int
        Exit code.
    """
    region = getattr(args, "region", DEFAULT_REGION)
    clients, tailscale = _make_clients_and_tailscale(region)
    lcc, _sr, _remote, _lc, _mc = factory(clients, tailscale)

    deployment = Deployment(name=args.name, model="flash", region=region)

    try:
        lcc.rotate_token(deployment)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_destroy(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the destroy subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory returning ``(lcc, sr, remote, lc, mc)``.

    Returns
    -------
    int
        Exit code.
    """
    region = getattr(args, "region", DEFAULT_REGION)
    clients, tailscale = _make_clients_and_tailscale(region)
    lcc, _sr, _remote, _lc, _mc = factory(clients, tailscale)

    deployment = Deployment(name=args.name, model="flash", region=region)
    confirm = getattr(args, "confirm", None)

    try:
        lcc.destroy(deployment, confirm)
        return 0
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 3
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_replace(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the replace subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory returning ``(lcc, sr, remote, lc, mc)``.

    Returns
    -------
    int
        Exit code.
    """
    region = getattr(args, "region", DEFAULT_REGION)
    clients, tailscale = _make_clients_and_tailscale(region)
    _lcc, _sr, _remote, lc, _mc = factory(clients, tailscale)

    deployment = Deployment(
        name=args.name, model=getattr(args, "model", "flash"), region=region
    )
    try:
        lc.replace(deployment)
        return 0
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def handle_verify(args: argparse.Namespace, factory: FactoryCallable) -> int:
    """Handle the verify subcommand.

    Reads the instance config from SSM, then runs the CUDA verification gate:
    on-instance tests and context probe via Tailscale SSH, followed by an
    operator-side eval run and report comparison.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.
    factory : FactoryCallable
        Dependency factory returning ``(lcc, sr, remote, lc, mc)``.

    Returns
    -------
    int
        Exit code.
    """
    region = getattr(args, "region", DEFAULT_REGION)
    clients, tailscale = _make_clients_and_tailscale(region)
    _lcc, _sr, remote, _lc, _mc = factory(clients, tailscale)

    names = DeploymentName(name=args.name)

    try:
        resp = clients.ssm.get_parameter(Name=names.config_param)
        config_data = json.loads(resp["Parameter"]["Value"])
        ember_version: str = config_data["ember_version"]
        model_s3_uri: str = config_data["model_s3_uri"]

        resp_token = clients.ssm.get_parameter(
            Name=names.token_param, WithDecryption=True
        )
        token: str = resp_token["Parameter"]["Value"]

        from pathlib import Path  # import-placement:allow

        from .sizing_table import SizingTable  # import-placement:allow
        from .status_reader import StatusReader  # import-placement:allow

        sizing_path = Path(__file__).parent.parent / "sizing.json"
        sizing = SizingTable.load(sizing_path)
        sr = StatusReader(clients=clients, tailscale=tailscale, sizing=sizing)
        status = sr.read(names)
        server_url: str = status.url or ""

        remote_obj = remote.__class__(names=names, runner=remote._runner)
        remote_obj.verify(
            ember_version=ember_version,
            model_s3_uri=model_s3_uri,
            server_url=server_url,
            token=token,
        )
        return 0
    except Exception as exc:
        if _is_parameter_not_found(exc):
            print(
                f"error: no deployment {args.name!r} found in {region} — deploy"
                f" it first (make aws-up NAME={args.name} REGION={region}), or"
                " pass the region where it runs"
                " (make aws-verify REGION=<region>).",
                file=sys.stderr,
            )
            return 2
        print(f"error: {exc}", file=sys.stderr)
        return 2
