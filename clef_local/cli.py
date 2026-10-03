"""The `clef` command-line interface: install, model, server, and opencode lifecycle."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import config, models, opencode_config, opencode_plugin, paths, process


def _emit(obj: object) -> None:
    print(json.dumps(obj, indent=2))


def _model_dir_or_fail(name: str | None) -> Path:
    resolved = models.resolve_dir(name or config.resolve("model"))
    if resolved is None:
        raise SystemExit(
            f"model {name or config.resolve('model')!r} is not pulled. Run: clef model pull"
        )
    return resolved


def _apply_server_env(args: argparse.Namespace) -> None:
    model_dir = _model_dir_or_fail(args.model)
    os.environ["CLEF_MODEL_DIR"] = str(model_dir)
    os.environ["CLEF_HOST"] = str(args.host or config.resolve("host"))
    os.environ["CLEF_PORT"] = str(args.port or config.resolve("port"))
    os.environ["CLEF_DEVICE"] = str(args.device or config.resolve("device"))


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
    print(f"clef server ready (pid {pid})")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    stopped = process.stop(args.host, args.port)
    print("stopped" if stopped else "not running")
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    pid = process.restart(args.model, args.host, args.port, args.device)
    print(f"clef server restarted (pid {pid})")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    host = args.host or config.resolve("host")
    port = int(args.port or config.resolve("port"))
    info = process.health(host, port)
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
    os.execvp("tail", ["tail", "-n", str(args.lines), "-f", str(log)])
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    if args.port:
        os.environ["CLEF_SERVER_URL"] = f"http://{args.host or config.resolve('host')}:{args.port}"
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
        answer = input(f"Remove model {args.name or models.DEFAULT}? [y/N] ").strip().lower()
        if answer != "y":
            print("aborted")
            return 1
    print(models.remove(args.name))
    return 0


# --------------------------------------------------------------------------- #
# config, init, doctor, uninstall
# --------------------------------------------------------------------------- #
def cmd_config_path(_: argparse.Namespace) -> int:
    print(paths.config_path())
    return 0


def cmd_config_show(_: argparse.Namespace) -> int:
    _emit(config.load())
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    host = str(args.host or config.resolve("host"))
    port = int(args.port or config.resolve("port"))
    autostart = "0" if args.no_autostart else "1"
    scope = "global" if args.global_ else "project"
    target = (
        opencode_config.global_config_path()
        if args.global_
        else opencode_config.project_config_path(Path.cwd())
    )
    command = opencode_config.mcp_command()
    path = opencode_config.write(target, host, port, autostart)
    print(f"wrote {path}")

    if args.opencode:
        plugin = opencode_plugin.install(command, f"http://{host}:{port}", scope=scope)
        print(f"installed opencode plugin: {plugin}")
    print(f"  command: {command}")
    print("restart opencode to pick up changes")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    ok = True

    def report(label: str, good: bool, detail: str = "") -> None:
        nonlocal ok
        mark = "OK " if good else "FAIL"
        print(f"[{mark}] {label}{': ' + detail if detail else ''}")
        ok = ok and good

    report("apple silicon", paths.is_apple_silicon(), "arm64 macOS")
    report("uv", bool(shutil.which("uv")), shutil.which("uv") or "not found")
    try:
        import torch

        mps = torch.backends.mps.is_available()
        report("torch", True, f"{torch.__version__} (mps={'yes' if mps else 'no'})")
    except Exception as exc:
        report("torch", False, str(exc))
    try:
        import transformers

        report("transformers", True, transformers.__version__)
    except Exception as exc:
        report("transformers", False, str(exc))
    try:
        from .runtime import DEFAULT_MODEL_DIR

        report("dev weights", DEFAULT_MODEL_DIR.is_dir(), str(DEFAULT_MODEL_DIR))
    except Exception:
        pass
    for row in models.list_models():
        if row["default"]:
            report(f"model {row['name']}", row["cached"], row["path"] or "not pulled")
        else:
            state = row["path"] if row["cached"] else "not pulled (optional)"
            print(f"[info] model {row['name']} ({row['params']}): {state}")
    info = process.health(config.resolve("host"), int(config.resolve("port")))
    report("server", info is not None, "running" if info else "not running")
    return 0 if ok else 1


def cmd_uninstall(args: argparse.Namespace) -> int:
    process.stop()
    if args.purge_models:
        for row in models.list_models():
            if row["cached"]:
                print(models.remove(row["name"]))
    for directory in (paths.state_dir(), paths.config_dir()):
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
            print(f"removed {directory}")
    print("run: uv tool uninstall clef-local")
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
    parser = argparse.ArgumentParser(prog="clef", description="Clef decision models, locally.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("serve", help="run the model server in the foreground")
    _add_server_flags(p)
    p.set_defaults(func=cmd_serve)

    for name, fn in (("start", cmd_start), ("stop", cmd_stop), ("restart", cmd_restart), ("status", cmd_status)):
        p = sub.add_parser(name)
        _add_server_flags(p)
        p.set_defaults(func=fn)

    p = sub.add_parser("logs")
    p.add_argument("-n", "--lines", type=int, default=40)
    p.set_defaults(func=cmd_logs)

    p = sub.add_parser("mcp", help="run the MCP stdio server (for opencode)")
    _add_server_flags(p)
    p.set_defaults(func=cmd_mcp)

    model = sub.add_parser("model", help="manage model weights")
    msub = model.add_subparsers(dest="model_command", required=True)
    p = msub.add_parser("pull")
    p.add_argument("name", nargs="?", default=models.DEFAULT)
    p.add_argument("--allow-low-disk", action="store_true")
    p.set_defaults(func=cmd_model_pull)
    p = msub.add_parser("list")
    p.set_defaults(func=cmd_model_list)
    p = msub.add_parser("path")
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_model_path)
    p = msub.add_parser("rm")
    p.add_argument("name", nargs="?")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=cmd_model_rm)

    cfg = sub.add_parser("config", help="inspect configuration")
    csub = cfg.add_subparsers(dest="config_command", required=True)
    p = csub.add_parser("path")
    p.set_defaults(func=cmd_config_path)
    p = csub.add_parser("show")
    p.set_defaults(func=cmd_config_show)

    p = sub.add_parser("init", help="register the MCP server with opencode")
    p.add_argument("--global", dest="global_", action="store_true")
    p.add_argument("--opencode", action="store_true", help="install the local opencode plugin")
    p.add_argument("--no-autostart", action="store_true")
    _add_server_flags(p)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("uninstall", help="stop the server and remove local state")
    p.add_argument("--purge-models", action="store_true")
    p.set_defaults(func=cmd_uninstall)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (RuntimeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
