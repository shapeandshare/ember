"""Eval subcommand handlers: eval run, report, export, snapshot, agent."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

_EVAL_CHECKOUT_ERROR = (
    "the `ember eval` commands require a repository checkout: `evals/eval/` is not "
    "part of the installed package. Run from a clone, or use `make eval-run` / "
    "`make eval-report`."
)

_RESULTS_FILE_HELP = "path to *_results.json (default: most recent in results/)"


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
        from evals.eval.run_evals import DEFAULT_SERVER, run_evals
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
        from evals.eval.report_evals import main as report_main
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
        from evals.eval.report_evals import main as report_main
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
        from evals.eval.snapshot_evals import main as snapshot_main
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
        ``evals/eval/run_agent_evals.py`` unchanged (try ``ember eval agent --help``).

    Returns
    -------
    int
        Exit code from ``run_agent_evals.main``.
    """
    try:
        from evals.eval.run_agent_evals import main as agent_main
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc
    return agent_main(list(args.agent_args))


def cmd_eval_context(args: argparse.Namespace) -> int:
    """Run the long-context probe (``ember eval context``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; ``args.context_args`` pass through to
        ``evals/context/run_context.py`` unchanged.

    Returns
    -------
    int
        Exit code from ``run_context.main``.
    """
    try:
        from evals.context.run_context import main as context_main
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc
    return context_main(list(args.context_args))
