"""The ``ember`` command line: server, models, opencode, and agent onboarding.

This module is the composition root: it wires argparse subcommands to the
handlers defined in ``ember/commands/``.
"""

from __future__ import annotations

import argparse
import sys

from .commands.agents import (
    cmd_agents_install,
    cmd_agents_show,
    cmd_init,
    cmd_uninstall,
)
from .commands.config import cmd_config_path, cmd_config_show
from .commands.doctor import cmd_doctor
from .commands.eval import (
    cmd_eval_agent,
    cmd_eval_export,
    cmd_eval_report,
    cmd_eval_run,
    cmd_eval_snapshot,
)
from .commands.lifecycle import (
    cmd_logs,
    cmd_mcp,
    cmd_restart,
    cmd_serve,
    cmd_start,
    cmd_status,
    cmd_stop,
)
from .commands.models import (
    cmd_model_list,
    cmd_model_path,
    cmd_model_pull,
    cmd_model_rm,
)
from .commands.parser import (
    add_endpoint_flag,
    register_agents,
    register_config,
    register_eval,
    register_lifecycle,
    register_model,
)


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
            "decision models on Apple Silicon."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check platform, dependencies, model, and server")
    add_endpoint_flag(p)
    p.set_defaults(func=cmd_doctor)

    register_lifecycle(
        sub,
        cmd_serve=cmd_serve,
        cmd_start=cmd_start,
        cmd_stop=cmd_stop,
        cmd_restart=cmd_restart,
        cmd_status=cmd_status,
        cmd_logs=cmd_logs,
        cmd_mcp=cmd_mcp,
    )
    register_model(
        sub,
        cmd_pull=cmd_model_pull,
        cmd_list=cmd_model_list,
        cmd_path=cmd_model_path,
        cmd_rm=cmd_model_rm,
    )
    register_config(sub, cmd_path=cmd_config_path, cmd_show=cmd_config_show)
    register_agents(
        sub,
        cmd_init=cmd_init,
        cmd_install=cmd_agents_install,
        cmd_show=cmd_agents_show,
        cmd_uninstall=cmd_uninstall,
    )
    register_eval(
        sub,
        cmd_run=cmd_eval_run,
        cmd_report=cmd_eval_report,
        cmd_export=cmd_eval_export,
        cmd_snapshot=cmd_eval_snapshot,
        cmd_agent=cmd_eval_agent,
    )

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
