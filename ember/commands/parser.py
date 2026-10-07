"""Argparse subcommand registration helpers for the ``ember`` CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import models as models_mod
from ..agent_kit import api as agent_kit
from ..commands.eval import _RESULTS_FILE_HELP


def add_server_flags(parser: argparse.ArgumentParser) -> None:
    """Add the common server flags to a subcommand parser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The subcommand parser to augment.
    """
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--device", choices=["auto", "mps", "cpu"])
    parser.add_argument(
        "--model",
        help="model name; one of the keys in the registry (e.g. flash, full)",
    )


def add_endpoint_flag(parser: argparse.ArgumentParser) -> None:
    """Add the ``--server-url`` flag to a subcommand parser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The subcommand parser to augment.
    """
    parser.add_argument(
        "--server-url",
        help="client inference endpoint (default: configured server_url)",
    )


def register_lifecycle(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
    cmd_serve: object,
    cmd_start: object,
    cmd_stop: object,
    cmd_restart: object,
    cmd_status: object,
    cmd_logs: object,
    cmd_mcp: object,
) -> None:
    """Register server lifecycle subcommands on ``sub``.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The top-level subparsers action to register commands on.
    cmd_serve : object
        Handler for ``ember serve``.
    cmd_start : object
        Handler for ``ember start``.
    cmd_stop : object
        Handler for ``ember stop``.
    cmd_restart : object
        Handler for ``ember restart``.
    cmd_status : object
        Handler for ``ember status``.
    cmd_logs : object
        Handler for ``ember logs``.
    cmd_mcp : object
        Handler for ``ember mcp``.
    """
    p = sub.add_parser("serve", help="run the model server in the foreground")
    add_server_flags(p)
    p.set_defaults(func=cmd_serve)

    for name, fn, help_text in (
        ("start", cmd_start, "start the model server in the background"),
        ("stop", cmd_stop, "stop the server started by `ember start`"),
        ("restart", cmd_restart, "restart the background model server"),
        ("status", cmd_status, "show server health (exit code 1 when stopped)"),
    ):
        p = sub.add_parser(name, help=help_text)
        add_server_flags(p)
        if name == "status":
            add_endpoint_flag(p)
        p.set_defaults(func=fn)

    p = sub.add_parser("logs", help="follow the model server log")
    p.add_argument("-n", "--lines", type=int, default=40)
    p.set_defaults(func=cmd_logs)

    p = sub.add_parser("mcp", help="run the MCP stdio server (agents launch this)")
    add_server_flags(p)
    p.set_defaults(func=cmd_mcp)


def register_model(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
    cmd_pull: object,
    cmd_list: object,
    cmd_path: object,
    cmd_rm: object,
) -> None:
    """Register ``ember model`` subcommands on ``sub``.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The top-level subparsers action to register commands on.
    cmd_pull : object
        Handler for ``ember model pull``.
    cmd_list : object
        Handler for ``ember model list``.
    cmd_path : object
        Handler for ``ember model path``.
    cmd_rm : object
        Handler for ``ember model rm``.
    """
    model = sub.add_parser("model", help="manage model weights")
    msub = model.add_subparsers(dest="model_command", required=True)
    p = msub.add_parser("pull", help="download the pinned weights (~18 GB for flash)")
    p.add_argument("name", nargs="?", default=models_mod.DEFAULT)
    p.add_argument("--allow-low-disk", action="store_true")
    p.set_defaults(func=cmd_pull)
    p = msub.add_parser("list", help="list models and where they are cached")
    p.set_defaults(func=cmd_list)
    p = msub.add_parser("path", help="print the directory a model runs from")
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_path)
    p = msub.add_parser("rm", help="delete a model's local files")
    p.add_argument("name", nargs="?")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=cmd_rm)


def register_config(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
    cmd_path: object,
    cmd_show: object,
) -> None:
    """Register ``ember config`` subcommands on ``sub``.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The top-level subparsers action to register commands on.
    cmd_path : object
        Handler for ``ember config path``.
    cmd_show : object
        Handler for ``ember config show``.
    """
    cfg = sub.add_parser("config", help="inspect configuration")
    csub = cfg.add_subparsers(dest="config_command", required=True)
    p = csub.add_parser("path", help="print the config file path")
    p.set_defaults(func=cmd_path)
    p = csub.add_parser("show", help="print the effective config")
    p.set_defaults(func=cmd_show)


def register_agents(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
    cmd_init: object,
    cmd_install: object,
    cmd_show: object,
    cmd_uninstall: object,
) -> None:
    """Register ``ember init``, ``ember agents``, and ``ember uninstall`` on ``sub``.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The top-level subparsers action to register commands on.
    cmd_init : object
        Handler for ``ember init``.
    cmd_install : object
        Handler for ``ember agents install``.
    cmd_show : object
        Handler for ``ember agents show``.
    cmd_uninstall : object
        Handler for ``ember uninstall``.
    """
    p = sub.add_parser(
        "init", help="register the MCP server with opencode (writes opencode.json)"
    )
    p.add_argument("--global", dest="global_", action="store_true")
    p.add_argument(
        "--opencode",
        action="store_true",
        help="also install the opencode plugin and skill",
    )
    p.add_argument("--no-autostart", action="store_true")
    add_server_flags(p)
    p.set_defaults(func=cmd_init)

    agents = sub.add_parser(
        "agents", help="onboard coding agents to use the advise tool"
    )
    asub = agents.add_subparsers(dest="agents_command", required=True)
    p = asub.add_parser(
        "install", help=f"install the {agent_kit.SKILL_NAME} skill for an agent"
    )
    p.add_argument("--agent", choices=agent_kit.AGENTS, default="opencode")
    p.add_argument("--global", dest="global_", action="store_true")
    p.set_defaults(func=cmd_install)
    p = asub.add_parser("show", help="print part of the onboarding kit")
    p.add_argument("what", choices=["instructions", "skill", "snippet"])
    p.set_defaults(func=cmd_show)

    p = sub.add_parser(
        "uninstall",
        help="stop the server and remove ember's state and global installs",
    )
    p.add_argument("--purge-models", action="store_true")
    p.set_defaults(func=cmd_uninstall)


def register_eval(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
    cmd_run: object,
    cmd_report: object,
    cmd_export: object,
    cmd_snapshot: object,
    cmd_agent: object,
) -> None:
    """Register ``ember eval`` subcommands on ``sub``.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The top-level subparsers action to register commands on.
    cmd_run : object
        Handler for ``ember eval run``.
    cmd_report : object
        Handler for ``ember eval report``.
    cmd_export : object
        Handler for ``ember eval export``.
    cmd_snapshot : object
        Handler for ``ember eval snapshot``.
    cmd_agent : object
        Handler for ``ember eval agent``.
    """
    eval_cmd = sub.add_parser("eval", help="calibration eval suite")
    esub = eval_cmd.add_subparsers(dest="eval_command", required=True)

    p = esub.add_parser("run", help="run the eval dataset against a live server")
    p.add_argument(
        "--server",
        default=None,
        help="model server URL (default: EMBER_SERVER_URL or http://127.0.0.1:8765)",
    )
    p.add_argument(
        "--split",
        choices=["dev", "test"],
        default=None,
        help="only items from this split (default: all)",
    )
    p.add_argument("--category", default=None, help="only items from this category")
    p.add_argument(
        "--dataset",
        default=str(Path(__file__).resolve().parents[2] / "evals" / "clef-flash.jsonl"),
        help="path to JSONL eval dataset",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print items without hitting the server",
    )
    p.set_defaults(func=cmd_run)

    p = esub.add_parser("report", help="render a results JSON as a Markdown table")
    p.add_argument("results_file", nargs="?", default=None, help=_RESULTS_FILE_HELP)
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.add_argument(
        "--compare",
        nargs=2,
        metavar=("RUN_A", "RUN_B"),
        default=None,
        help="compare two results files side-by-side",
    )
    p.set_defaults(func=cmd_report)

    p = esub.add_parser(
        "export",
        help="write a reviewer bundle: Markdown and HTML report, figures, raw data",
    )
    p.add_argument("results_file", nargs="?", default=None, help=_RESULTS_FILE_HELP)
    p.add_argument(
        "--out",
        default=None,
        help="bundle directory (default: results/<run_id>_report/)",
    )
    p.add_argument(
        "--agent",
        default=None,
        help="attach an agent-in-the-loop run: an agent_*_results.json, or 'latest'",
    )
    p.set_defaults(func=cmd_export)

    p = esub.add_parser(
        "snapshot",
        help="copy a run into the tracked benchmark/ bundle the site renders",
    )
    p.add_argument("results_file", nargs="?", default=None, help=_RESULTS_FILE_HELP)
    p.set_defaults(func=cmd_snapshot)

    p = esub.add_parser(
        "agent",
        add_help=False,
        help="agent-in-the-loop eval: opencode on scripted scenarios (opt-in, "
        "uses provider API credit)",
    )
    p.add_argument("agent_args", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_agent)
