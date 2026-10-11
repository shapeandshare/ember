"""Argparse subcommand registration helpers for the ember_aws CLI.

Each ``_add_*`` function registers one subcommand (or subcommand group) on
the top-level subparsers action.  Imported by ``__main__`` to keep that
module under the 400-line limit (Article X §10.3).
"""

from __future__ import annotations

import argparse
from typing import Any

from ._cli_handlers import (
    handle_cache_add,
    handle_cache_destroy,
    handle_cache_dispatch,
    handle_cache_list,
    handle_cache_rm,
    handle_deploy,
    handle_preflight,
    handle_token,
)
from ._cli_handlers_control import (
    handle_destroy,
    handle_logs,
    handle_replace,
    handle_rotate_token,
    handle_ssh,
    handle_start,
    handle_status,
    handle_stop,
    handle_verify,
)
from .defaults import DEFAULT_REGION


def add_common(p: argparse.ArgumentParser) -> None:
    """Add common flags shared by most subcommands.

    Parameters
    ----------
    p : argparse.ArgumentParser
        The subcommand parser to extend.
    """
    p.add_argument("--region", default=DEFAULT_REGION, help="AWS region")


def add_deployment_flags(p: argparse.ArgumentParser) -> None:
    """Add deployment-identity flags.

    Parameters
    ----------
    p : argparse.ArgumentParser
        The subcommand parser to extend.
    """
    p.add_argument("--name", default="default", help="Deployment name")
    p.add_argument("--model", default="flash", help="Model key (flash|full)")


def add_preflight(sub: Any) -> None:
    """Register the preflight subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser("preflight", help="Run all preflight checks")
    add_common(p)
    add_deployment_flags(p)
    p.add_argument("--instance-type", default=None, help="EC2 instance type")
    p.set_defaults(handler=handle_preflight)


def add_cache(sub: Any) -> None:
    """Register the cache subcommand group.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser("cache", help="Manage the S3 model cache")
    cache_sub = p.add_subparsers(dest="cache_command")

    add_p = cache_sub.add_parser("add", help="Upload a model to the cache")
    add_common(add_p)
    add_p.add_argument("--model", default="flash", help="Model key")
    add_p.add_argument(
        "--bucket", default=None, help="S3 bucket (skips stack creation)"
    )
    add_p.add_argument("--prefix", default="models/", help="S3 key prefix")
    add_p.set_defaults(handler=handle_cache_add)

    list_p = cache_sub.add_parser("list", help="List cached models")
    add_common(list_p)
    list_p.add_argument("--bucket", default=None, help="S3 bucket")
    list_p.add_argument("--prefix", default="models/", help="S3 key prefix")
    list_p.set_defaults(handler=handle_cache_list)

    rm_p = cache_sub.add_parser("rm", help="Remove a cached model")
    add_common(rm_p)
    rm_p.add_argument("--model", required=True, help="Model key")
    rm_p.add_argument("--revision", required=True, help="Model revision")
    rm_p.add_argument("--bucket", default=None, help="S3 bucket")
    rm_p.add_argument("--prefix", default="models/", help="S3 key prefix")
    rm_p.set_defaults(handler=handle_cache_rm)

    destroy_p = cache_sub.add_parser("destroy", help="Delete the cache bucket")
    add_common(destroy_p)
    destroy_p.add_argument("--confirm", required=True, help="Bucket name to confirm")
    destroy_p.add_argument("--bucket", default=None, help="S3 bucket")
    destroy_p.set_defaults(handler=handle_cache_destroy)

    p.set_defaults(handler=handle_cache_dispatch)


def add_deploy(sub: Any) -> None:
    """Register the deploy subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser("deploy", help="Deploy (or update) the ember GPU instance")
    add_common(p)
    add_deployment_flags(p)
    p.add_argument("--instance-type", default=None, help="EC2 instance type")
    p.add_argument(
        "--capacity",
        default="on-demand",
        choices=["on-demand", "spot"],
        help="Capacity type",
    )
    p.add_argument(
        "--idle-minutes", type=int, default=0, help="Idle stop minutes (0=off)"
    )
    p.add_argument("--ember-version", default="", help="ember-advise version to pin")
    p.set_defaults(handler=handle_deploy)


def add_token(sub: Any) -> None:
    """Register the token subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser("token", help="Print the server auth token")
    add_common(p)
    add_deployment_flags(p)
    p.set_defaults(handler=handle_token)


def add_status(sub: Any) -> None:
    """Register the status subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser("status", help="Show deployment state, instance, URL, and cost")
    add_common(p)
    p.add_argument("--name", default="default", help="Deployment name")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(handler=handle_status)


def add_stop(sub: Any) -> None:
    """Register the stop subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser("stop", help="Stop the EC2 instance and wait for stopped state")
    add_common(p)
    p.add_argument("--name", default="default", help="Deployment name")
    p.set_defaults(handler=handle_stop)


def add_start(sub: Any) -> None:
    """Register the start subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser("start", help="Start the instance and wait for health")
    add_common(p)
    p.add_argument("--name", default="default", help="Deployment name")
    p.set_defaults(handler=handle_start)


def add_logs(sub: Any) -> None:
    """Register the logs subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser("logs", help="Stream instance logs via Tailscale SSH")
    p.add_argument("--name", default="default", help="Deployment name")
    p.add_argument(
        "--unit",
        default="ember",
        choices=["ember", "converge", "idle", "tailscale"],
        help="Systemd unit to stream (default: ember)",
    )
    p.add_argument("--follow", action="store_true", help="Follow the journal live")
    p.set_defaults(handler=handle_logs)


def add_ssh(sub: Any) -> None:
    """Register the ssh subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser("ssh", help="Open a Tailscale SSH shell on the instance")
    p.add_argument("--name", default="default", help="Deployment name")
    p.set_defaults(handler=handle_ssh)


def add_rotate_token(sub: Any) -> None:
    """Register the rotate-token subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser(
        "rotate-token", help="Generate a new server token and reboot the instance"
    )
    add_common(p)
    p.add_argument("--name", default="default", help="Deployment name")
    p.set_defaults(handler=handle_rotate_token)


def add_destroy(sub: Any) -> None:
    """Register the destroy subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser(
        "destroy",
        help="Destroy the deployment (keeps the cache). Pass --confirm <name>.",
    )
    add_common(p)
    p.add_argument("--name", default="default", help="Deployment name")
    p.add_argument(
        "--confirm",
        required=True,
        help="Deployment name to confirm destruction",
    )
    p.set_defaults(handler=handle_destroy)


def add_replace(sub: Any) -> None:
    """Register the replace subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser(
        "replace",
        help="Replace the instance with the latest DLAMI and wait for health",
    )
    add_common(p)
    p.add_argument("--name", default="default", help="Deployment name")
    p.add_argument("--model", default="flash", help="Model name")
    p.set_defaults(handler=handle_replace)


def add_verify(sub: Any) -> None:
    """Register the verify subcommand.

    Parameters
    ----------
    sub : Any
        The subparsers action to add to.
    """
    p = sub.add_parser(
        "verify",
        help="Run the CUDA verification gate over Tailscale SSH and benchmark",
    )
    add_common(p)
    p.add_argument("--name", default="default", help="Deployment name")
    p.set_defaults(handler=handle_verify)
