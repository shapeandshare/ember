"""The `ember` command line: server, models, opencode, and agent onboarding."""

from __future__ import annotations

import argparse
import collections
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

from . import (
    agent_kit,
    config,
    models,
    opencode_config,
    opencode_plugin,
    paths,
    process,
)


def _emit(obj: object) -> None:
    print(json.dumps(obj, indent=2))


def _host_port(args: argparse.Namespace) -> tuple[str, int]:
    return str(args.host or config.resolve("host")), int(
        args.port or config.resolve("port")
    )


def _apply_server_env(args: argparse.Namespace) -> None:
    name = args.model or config.resolve("model")
    model_dir = models.resolve_dir(name)
    if model_dir is None:
        raise SystemExit(f"model {name!r} is not pulled; run: ember model pull {name}")
    host, port = _host_port(args)
    os.environ["EMBER_MODEL_DIR"] = str(model_dir)
    os.environ["EMBER_HOST"] = host
    os.environ["EMBER_PORT"] = str(port)
    os.environ["EMBER_DEVICE"] = str(args.device or config.resolve("device"))


# --------------------------------------------------------------------------- #
# server lifecycle
# --------------------------------------------------------------------------- #
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
    from . import server

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
    host, port = _host_port(args)
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
    """Print server health (``ember status``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags.

    Returns
    -------
    int
        ``0`` if running, ``1`` if stopped.
    """
    info = process.health(*_host_port(args))
    if info is None:
        print("not running")
        return 1
    _emit(info)
    return 0


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
        host, port = _host_port(args)
        os.environ["EMBER_SERVER_URL"] = f"http://{host}:{port}"
    if args.device:
        os.environ["EMBER_DEVICE"] = args.device
    if args.model:
        os.environ["EMBER_MODEL"] = args.model
    from . import mcp_server

    mcp_server.main()
    return 0


# --------------------------------------------------------------------------- #
# model lifecycle
# --------------------------------------------------------------------------- #
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
    path = models.pull(args.name, allow_low_disk=args.allow_low_disk)
    print(f"{args.name or models.DEFAULT} ready at {path}")
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
    _emit(models.list_models())
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
    resolved = models.resolve_dir(args.name)
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
            input(f"Remove model {args.name or models.DEFAULT}? [y/N] ").strip().lower()
        )
        if answer != "y":
            print("aborted")
            return 1
    print(models.remove(args.name))
    return 0


# --------------------------------------------------------------------------- #
# config, opencode, agents
# --------------------------------------------------------------------------- #
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
    """Print the effective config (``ember config show``).

    Parameters
    ----------
    _ : argparse.Namespace
        Parsed CLI arguments (unused).

    Returns
    -------
    int
        Always ``0``.
    """
    _emit(config.load())
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Register the MCP server with opencode (``ember init``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags plus ``args.global_``,
        ``args.opencode``, and ``args.no_autostart``.

    Returns
    -------
    int
        Always ``0``.
    """
    host, port = _host_port(args)
    autostart = "0" if args.no_autostart else "1"
    scope = "global" if args.global_ else "project"
    target = (
        opencode_config.global_config_path()
        if args.global_
        else opencode_config.project_config_path(Path.cwd())
    )
    command = opencode_config.mcp_command()
    print(f"wrote {opencode_config.write(target, host, port, autostart)}")
    if args.opencode:
        plugin = opencode_plugin.install(command, f"http://{host}:{port}", scope=scope)
        print(f"installed opencode plugin: {plugin}")
        skill = agent_kit.install_skill("opencode", scope, Path.cwd())
        print(f"installed {agent_kit.SKILL_NAME} skill: {skill}")
    print(f"  command: {command}")
    print("restart opencode to pick up changes")
    return 0


def cmd_agents_install(args: argparse.Namespace) -> int:
    """Install the onboarding skill for an agent (``ember agents install``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.agent`` and ``args.global_``.

    Returns
    -------
    int
        Always ``0``.
    """
    scope = "global" if args.global_ else "project"
    path = agent_kit.install_skill(args.agent, scope, Path.cwd())
    print(f"installed {agent_kit.SKILL_NAME} skill for {args.agent}: {path}")
    return 0


def cmd_agents_show(args: argparse.Namespace) -> int:
    """Print part of the onboarding kit (``ember agents show``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.what`` (``"instructions"``,
        ``"skill"``, or ``"snippet"``).

    Returns
    -------
    int
        Always ``0``.
    """
    text = {
        "instructions": agent_kit.instructions,
        "skill": agent_kit.skill,
        "snippet": agent_kit.snippet,
    }[args.what]()
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


# --------------------------------------------------------------------------- #
# doctor, uninstall
# --------------------------------------------------------------------------- #
def cmd_doctor(_: argparse.Namespace) -> int:
    """Check platform, dependencies, model, and server (``ember doctor``).

    Parameters
    ----------
    _ : argparse.Namespace
        Parsed CLI arguments (unused).

    Returns
    -------
    int
        ``0`` if every check passed, ``1`` otherwise.
    """
    ok = True

    def check(label: str, good: bool, detail: str) -> None:
        nonlocal ok
        print(f"[{'ok' if good else 'FAIL'}] {label}: {detail}")
        ok = ok and good

    def info(label: str, detail: str) -> None:
        print(f"[info] {label}: {detail}")

    supported = paths.is_apple_silicon()
    check(
        "platform",
        supported,
        "Apple Silicon macOS"
        if supported
        else f"{sys.platform}/{platform.machine()} is unsupported",
    )
    tested_python = sys.version_info[:2] == (3, 12)
    check(
        "python",
        tested_python,
        platform.python_version()
        if tested_python
        else f"{platform.python_version()} is untested; "
        "reinstall with `uv tool install --python 3.12 ...`",
    )
    try:
        import torch

        mps = torch.backends.mps.is_available()
        check(
            "torch",
            True,
            f"{torch.__version__} (mps={'yes' if mps else 'no, CPU fallback'})",
        )
    except Exception as exc:
        check("torch", False, str(exc))
    try:
        import transformers

        check("transformers", True, transformers.__version__)
    except Exception as exc:
        check("transformers", False, str(exc))

    selected = config.resolve("model")
    model_dir = models.resolve_dir(selected)
    check(
        f"model {selected}",
        model_dir is not None,
        str(model_dir)
        if model_dir
        else f"not pulled; run: ember model pull {selected}",
    )
    for row in models.list_models():
        if row["name"] != selected:
            info(
                f"model {row['name']} ({row['params']})",
                row["path"] or "not pulled (optional)",
            )

    host, port = config.resolve("host"), int(config.resolve("port"))
    running = process.health(host, port) is not None
    info(
        "server",
        f"running at {host}:{port}"
        if running
        else "stopped; starts on first use or with `ember start`",
    )
    info("opencode", shutil.which("opencode") or "not on PATH")
    return 0 if ok else 1


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Stop the server and remove global installs (``ember uninstall``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.purge_models``.

    Returns
    -------
    int
        Always ``0``.
    """
    if process.stop():
        print("stopped the model server")
    if args.purge_models:
        for row in models.list_models():
            if row["cached"]:
                print(models.remove(row["name"]))

    global_plugin = (
        opencode_plugin.plugin_dir("global") / opencode_plugin.PLUGIN_FILENAME
    )
    if global_plugin.exists():
        global_plugin.unlink()
        print(f"removed {global_plugin}")
    for agent in agent_kit.AGENTS:
        skill_dir = agent_kit.skill_path(agent, "global").parent
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
            print(f"removed {skill_dir}")
    if opencode_config.remove(opencode_config.global_config_path()):
        print(f"removed mcp.ember from {opencode_config.global_config_path()}")
    for directory in {paths.state_dir(), paths.config_dir()}:
        shutil.rmtree(directory, ignore_errors=True)
        print(f"removed {directory}")

    print(
        "project installs are left in place: in each initialized project, remove the "
        "`mcp.ember` entry from opencode.json, "
        f".opencode/plugins/{opencode_plugin.PLUGIN_FILENAME}, "
        f"and any {agent_kit.SKILL_NAME} skill directories"
    )
    print("then run: uv tool uninstall gut")
    return 0


# --------------------------------------------------------------------------- #
# eval
# --------------------------------------------------------------------------- #
_EVAL_CHECKOUT_ERROR = (
    "the `ember eval` commands require a repository checkout: `scripts/` is not "
    "part of the installed package. Run from a clone, or use `make eval-run` / "
    "`make eval-report`."
)


def cmd_eval_run(args: argparse.Namespace) -> int:
    """Run the eval dataset against a live server (``ember eval run``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.server``, ``args.split``,
        ``args.category``, ``args.dry_run``, and ``args.dataset``.

    Returns
    -------
    int
        Exit code from ``run_evals``.
    """
    try:
        from scripts.run_evals import DEFAULT_SERVER, run_evals
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc

    return run_evals(
        args.server or os.environ.get("EMBER_SERVER_URL", DEFAULT_SERVER),
        split=args.split,
        category=args.category,
        dry_run=args.dry_run,
        dataset_path=Path(args.dataset),
    )


def cmd_eval_report(args: argparse.Namespace) -> int:
    """Render a results JSON as a table (``ember eval report``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.results_file``, ``args.format``,
        and ``args.compare``.

    Returns
    -------
    int
        Exit code from ``report_evals.main``.
    """
    try:
        from scripts.report_evals import main as report_main
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc

    argv: list[str] = []
    if args.results_file:
        argv.append(str(args.results_file))
    if args.format:
        argv += ["--format", args.format]
    if args.compare:
        argv += ["--compare"] + [str(p) for p in args.compare]
    return report_main(argv)


def cmd_eval_export(args: argparse.Namespace) -> int:
    """Write the reviewer report bundle (``ember eval export``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.results_file``, ``args.out``, and
        ``args.agent``.

    Returns
    -------
    int
        Exit code from ``report_evals.main``.
    """
    try:
        from scripts.report_evals import main as report_main
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc

    argv = ["--export"]
    if args.results_file:
        argv.append(str(args.results_file))
    if args.out:
        argv += ["--out", str(args.out)]
    if args.agent:
        argv += ["--agent", str(args.agent)]
    return report_main(argv)


def cmd_eval_snapshot(args: argparse.Namespace) -> int:
    """Snapshot a run into the tracked benchmark bundle (``ember eval snapshot``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.results_file``.

    Returns
    -------
    int
        Exit code from ``snapshot_evals.main``.
    """
    try:
        from scripts.snapshot_evals import main as snapshot_main
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc
    argv = [str(args.results_file)] if args.results_file else []
    return snapshot_main(argv)


def cmd_eval_agent(args: argparse.Namespace) -> int:
    """Run the agent-in-the-loop eval through opencode (``ember eval agent``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; ``args.agent_args`` pass through to
        ``scripts/run_agent_evals.py`` unchanged (try ``ember eval agent --help``).

    Returns
    -------
    int
        Exit code from ``run_agent_evals.main``.
    """
    try:
        from scripts.run_agent_evals import main as agent_main
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc
    return agent_main(list(args.agent_args))


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def _add_server_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--device", choices=["auto", "mps", "cpu"])
    parser.add_argument("--model", help="model name (flash|full)")


def build_parser() -> argparse.ArgumentParser:
    """Build the ``ember`` command's argument parser.

    Returns
    -------
    argparse.ArgumentParser
        The fully configured parser, with all subcommands registered.
    """
    parser = argparse.ArgumentParser(
        prog="ember",
        description=(
            "A local gut feeling for coding agents: calibrated advice from "
            "Cloudflare's Clef model on Apple Silicon."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check platform, dependencies, model, and server")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("serve", help="run the model server in the foreground")
    _add_server_flags(p)
    p.set_defaults(func=cmd_serve)

    lifecycle = (
        ("start", cmd_start, "start the model server in the background"),
        ("stop", cmd_stop, "stop the server started by `ember start`"),
        ("restart", cmd_restart, "restart the background model server"),
        ("status", cmd_status, "show server health (exit code 1 when stopped)"),
    )
    for name, fn, help_text in lifecycle:
        p = sub.add_parser(name, help=help_text)
        _add_server_flags(p)
        p.set_defaults(func=fn)

    p = sub.add_parser("logs", help="follow the model server log")
    p.add_argument("-n", "--lines", type=int, default=40)
    p.set_defaults(func=cmd_logs)

    p = sub.add_parser("mcp", help="run the MCP stdio server (agents launch this)")
    _add_server_flags(p)
    p.set_defaults(func=cmd_mcp)

    model = sub.add_parser("model", help="manage model weights")
    msub = model.add_subparsers(dest="model_command", required=True)
    p = msub.add_parser("pull", help="download the pinned weights (~18 GB for flash)")
    p.add_argument("name", nargs="?", default=models.DEFAULT)
    p.add_argument("--allow-low-disk", action="store_true")
    p.set_defaults(func=cmd_model_pull)
    p = msub.add_parser("list", help="list models and where they are cached")
    p.set_defaults(func=cmd_model_list)
    p = msub.add_parser("path", help="print the directory a model runs from")
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_model_path)
    p = msub.add_parser("rm", help="delete a model's local files")
    p.add_argument("name", nargs="?")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=cmd_model_rm)

    cfg = sub.add_parser("config", help="inspect configuration")
    csub = cfg.add_subparsers(dest="config_command", required=True)
    p = csub.add_parser("path", help="print the config file path")
    p.set_defaults(func=cmd_config_path)
    p = csub.add_parser("show", help="print the effective config")
    p.set_defaults(func=cmd_config_show)

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
    _add_server_flags(p)
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
    p.set_defaults(func=cmd_agents_install)
    p = asub.add_parser("show", help="print part of the onboarding kit")
    p.add_argument("what", choices=["instructions", "skill", "snippet"])
    p.set_defaults(func=cmd_agents_show)

    p = sub.add_parser(
        "uninstall",
        help="stop the server and remove ember's state and global installs",
    )
    p.add_argument("--purge-models", action="store_true")
    p.set_defaults(func=cmd_uninstall)

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
        default=str(Path(__file__).resolve().parents[1] / "evals" / "clef-flash.jsonl"),
        help="path to JSONL eval dataset",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print items without hitting the server",
    )
    p.set_defaults(func=cmd_eval_run)

    p = esub.add_parser("report", help="render a results JSON as a Markdown table")
    p.add_argument(
        "results_file",
        nargs="?",
        default=None,
        help="path to *_results.json (default: most recent in results/)",
    )
    p.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
    )
    p.add_argument(
        "--compare",
        nargs=2,
        metavar=("RUN_A", "RUN_B"),
        default=None,
        help="compare two results files side-by-side",
    )
    p.set_defaults(func=cmd_eval_report)

    p = esub.add_parser(
        "export",
        help="write a reviewer bundle: Markdown and HTML report, figures, raw data",
    )
    p.add_argument(
        "results_file",
        nargs="?",
        default=None,
        help="path to *_results.json (default: most recent in results/)",
    )
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
    p.set_defaults(func=cmd_eval_export)

    p = esub.add_parser(
        "snapshot",
        help="copy a run into the tracked benchmark/ bundle the site renders",
    )
    p.add_argument(
        "results_file",
        nargs="?",
        default=None,
        help="path to *_results.json (default: most recent in results/)",
    )
    p.set_defaults(func=cmd_eval_snapshot)

    p = esub.add_parser(
        "agent",
        add_help=False,
        help="agent-in-the-loop eval: opencode on scripted scenarios (opt-in, "
        "uses provider API credit)",
    )
    p.add_argument("agent_args", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_eval_agent)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the selected subcommand.

    Parameters
    ----------
    argv : list[str] | None, optional
        Argument vector to parse; defaults to ``sys.argv[1:]`` via argparse.

    Returns
    -------
    int
        The subcommand's exit code, ``130`` on ``KeyboardInterrupt``, or
        ``1`` on a ``RuntimeError``/``KeyError``.
    """
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    if extra and getattr(args, "func", None) is not cmd_eval_agent:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    if extra:
        args.agent_args = [*extra, *args.agent_args]
    try:
        code: int = args.func(args)
        return code
    except KeyboardInterrupt:
        return 130
    except (RuntimeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
