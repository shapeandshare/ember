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
    _apply_server_env(args)
    from . import server

    server.main()
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    pid = process.start(args.model, args.host, args.port, args.device)
    print(f"ember server ready (pid {pid})")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
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
    pid = process.restart(args.model, args.host, args.port, args.device)
    print(f"ember server restarted (pid {pid})")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    info = process.health(*_host_port(args))
    if info is None:
        print("not running")
        return 1
    _emit(info)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
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
    path = models.pull(args.name, allow_low_disk=args.allow_low_disk)
    print(f"{args.name or models.DEFAULT} ready at {path}")
    return 0


def cmd_model_list(_: argparse.Namespace) -> int:
    _emit(models.list_models())
    return 0


def cmd_model_path(args: argparse.Namespace) -> int:
    resolved = models.resolve_dir(args.name)
    if resolved is None:
        print("not pulled")
        return 1
    print(resolved)
    return 0


def cmd_model_rm(args: argparse.Namespace) -> int:
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
    print(paths.config_path())
    return 0


def cmd_config_show(_: argparse.Namespace) -> int:
    _emit(config.load())
    return 0


def cmd_init(args: argparse.Namespace) -> int:
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
    scope = "global" if args.global_ else "project"
    path = agent_kit.install_skill(args.agent, scope, Path.cwd())
    print(f"installed {agent_kit.SKILL_NAME} skill for {args.agent}: {path}")
    return 0


def cmd_agents_show(args: argparse.Namespace) -> int:
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
# parser
# --------------------------------------------------------------------------- #
def _add_server_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--device", choices=["auto", "mps", "cpu"])
    parser.add_argument("--model", help="model name (flash|full)")


def build_parser() -> argparse.ArgumentParser:
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

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
