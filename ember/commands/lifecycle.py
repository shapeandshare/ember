"""Server lifecycle subcommand handlers: serve, start, stop, restart, logs, mcp."""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path

from .. import models
from ..cfg import config, paths
from ..cfg import endpoint as endpoint_mod
from ..serving import hosted, process
from .endpoint import endpoint_status, host_port, resolve_endpoint


def _apply_server_env(args: argparse.Namespace) -> None:
    """Set environment variables consumed by the model server process.

    Checks ``ember.serving.hosted.resolve()`` first: a hosted deployment
    (e.g. Outerbounds) runs ``ember serve`` directly, in the foreground,
    with ``EMBER_MODEL_S3_URI`` set and no ``REGISTRY`` entry ever pulled —
    the same precedence ``server.py``'s ``lifespan()`` and
    ``ember.serving.process.start()`` already apply.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags.

    Raises
    ------
    SystemExit
        If neither a hosted model location nor a pulled registry entry is
        available.
    """
    hosted_source = hosted.resolve()
    model_dir: Path | None
    if hosted_source is not None:
        model_dir = hosted_source.model_dir
    else:
        name = args.model or config.resolve("model")
        model_dir = models.resolve_dir(name)
        if model_dir is None:
            raise SystemExit(
                f"model {name!r} is not pulled; run: ember model pull {name}"
            )
    host, port = host_port(args)
    os.environ["EMBER_MODEL_DIR"] = str(model_dir)
    os.environ["EMBER_HOST"] = host
    os.environ["EMBER_PORT"] = str(port)
    os.environ["EMBER_DEVICE"] = str(args.device or config.resolve("device"))


def cmd_serve(args: argparse.Namespace) -> int:
    """Run the model server in the foreground (``ember serve``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags.

    Returns
    -------
    int
        Always ``0`` (the process exits when the server stops).
    """
    _apply_server_env(args)
    # import-placement:allow - defers torch/model load to serve subcommand only
    from ..serving import server

    server.main()
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Start the model server in the background (``ember start``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags.

    Returns
    -------
    int
        Always ``0``.
    """
    pid = process.start(args.model, args.host, args.port, args.device)
    print(f"ember server ready (pid {pid})")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the server started by ``ember start`` (``ember stop``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags.

    Returns
    -------
    int
        ``0`` if stopped or already not running; ``1`` if a server is up
        but was not started by ``ember start``.
    """
    host, port = host_port(args)
    if process.stop(host, port):
        print("stopped")
        return 0
    info = process.health(host, port)
    if info is not None:
        print(
            f"an ember server is running at {host}:{port} "
            f"(pid {info.get('pid')}) but was not started by `ember start`; "
            "stop it where it runs"
        )
        return 1
    print("not running")
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    """Restart the background model server (``ember restart``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags.

    Returns
    -------
    int
        Always ``0``.
    """
    pid = process.restart(args.model, args.host, args.port, args.device)
    print(f"ember server restarted (pid {pid})")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Print endpoint health (``ember status``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``--server-url`` or the server flags.

    Returns
    -------
    int
        ``0`` if the endpoint is reachable, ``1`` otherwise.
    """
    try:
        endpoint = resolve_endpoint(args)
    except (
        endpoint_mod.InvalidEndpointError,
        endpoint_mod.InsecureEndpointError,
    ) as exc:
        print(f"[fail] {exc}")
        return 1
    status = endpoint_status(endpoint)
    print(json.dumps(status, indent=2))
    return 0 if status["reachable"] else 1


def cmd_logs(args: argparse.Namespace) -> int:
    """Follow the model server log (``ember logs``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.lines`` for the initial tail size.

    Returns
    -------
    int
        ``1`` if no log file exists yet; otherwise runs until interrupted.
    """
    log = paths.server_log_path()
    if not log.exists():
        print(f"no log yet at {log}")
        return 1
    with log.open(errors="replace") as handle:
        sys.stdout.writelines(collections.deque(handle, maxlen=args.lines))
        sys.stdout.flush()
        while True:
            line = handle.readline()
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                time.sleep(0.5)


def cmd_mcp(args: argparse.Namespace) -> int:
    """Run the MCP stdio server (``ember mcp``); agents launch this.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags to set env vars for the
        MCP server before it starts.

    Returns
    -------
    int
        Always ``0`` (the process exits when the MCP client disconnects).
    """
    if args.host or args.port:
        host, port = host_port(args)
        client_host = "127.0.0.1" if host == "0.0.0.0" else host  # noqa: S104  # nosec B104 - comparing against the string to normalise it, not binding
        client_url = f"http://{client_host}:{port}"  # NOSONAR - loopback only
        os.environ["EMBER_SERVER_URL"] = client_url
    if args.device:
        os.environ["EMBER_DEVICE"] = args.device
    if args.model:
        os.environ["EMBER_MODEL"] = args.model
    # import-placement:allow - defers torch/model load to mcp subcommand only
    from ..mcp import mcp_server

    mcp_server.main()
    return 0
