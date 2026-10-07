"""Endpoint resolution and health-probe helpers shared by CLI subcommands."""

from __future__ import annotations

import argparse
from typing import Any

import httpx

from ..cfg import config
from ..cfg import endpoint as endpoint_mod
from ..serving import process


def host_port(args: argparse.Namespace) -> tuple[str, int]:
    """Resolve host and port from CLI args or config.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; may carry ``args.host`` and ``args.port``.

    Returns
    -------
    tuple[str, int]
        Resolved ``(host, port)`` pair.
    """
    return str(args.host or config.resolve("host")), int(
        args.port or config.resolve("port")
    )


def resolve_endpoint(args: argparse.Namespace) -> endpoint_mod.Endpoint:
    """Resolve the client endpoint from flags or config.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; may carry ``args.server_url``, ``args.host``,
        and ``args.port``.

    Returns
    -------
    endpoint_mod.Endpoint
        The resolved endpoint.
    """
    url = getattr(args, "server_url", None)
    if not url and (getattr(args, "host", None) or getattr(args, "port", None)):
        host, port = host_port(args)
        scheme = "http" if endpoint_mod.is_loopback_host(host) else "https"
        url = f"{scheme}://{host}:{port}"
    return endpoint_mod.Endpoint.resolve(url=url)


def remote_health(endpoint: endpoint_mod.Endpoint) -> dict[str, Any] | None:
    """Probe a remote endpoint's ``/health``; return the body or ``None``.

    Parameters
    ----------
    endpoint : endpoint_mod.Endpoint
        The endpoint to probe.

    Returns
    -------
    dict[str, Any] | None
        The parsed JSON body on HTTP 200, or ``None`` on any error.
    """
    try:
        resp = httpx.get(
            f"{endpoint.url}/health", timeout=min(endpoint.request_timeout, 5.0)
        )
        if resp.status_code == 200:
            body: dict[str, Any] = resp.json()
            return body
    except (httpx.HTTPError, ValueError):
        return None
    return None


def endpoint_status(endpoint: endpoint_mod.Endpoint) -> dict[str, Any]:
    """Report endpoint kind, reachability, and advertised contract/auth state.

    Parameters
    ----------
    endpoint : endpoint_mod.Endpoint
        The endpoint to inspect.

    Returns
    -------
    dict[str, Any]
        Status dict with keys ``kind``, ``url``, ``reachable``, ``ready``,
        ``contract_version``, ``remote_auth_required``, and ``auth_configured``.
    """
    status: dict[str, Any] = {
        "kind": "local" if endpoint.is_local else "remote",
        "url": endpoint.url,
        "reachable": False,
        "ready": None,
        "contract_version": None,
        "remote_auth_required": None,
        "auth_configured": bool(config.resolve("auth_token")),
    }
    body = (
        process.health(endpoint.host, endpoint.port)
        if endpoint.is_local
        else remote_health(endpoint)
    )
    if body is not None:
        status["reachable"] = True
        status["ready"] = body.get("status")
        status["contract_version"] = body.get("version")
        status["remote_auth_required"] = body.get("auth_required")
    return status
