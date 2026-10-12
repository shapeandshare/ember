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
        ``args.category``, ``args.dry_run``, ``args.dataset``, and
        ``args.deployment_label``.

    Returns
    -------
    int
        Exit code from ``run_evals``.
    """
    try:
        from evals.eval.client import DEFAULT_SERVER
        from evals.eval.run_evals import run_evals
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc

    return run_evals(
        args.server or os.environ.get("EMBER_SERVER_URL", DEFAULT_SERVER),
        split=args.split,
        category=args.category,
        dry_run=args.dry_run,
        dataset_path=Path(args.dataset),
        resume=getattr(args, "resume", None),
        deployment_label=(
            getattr(args, "deployment_label", None)
            or os.environ.get("EMBER_DEPLOYMENT_LABEL")
        ),
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
    if getattr(args, "rebuild", None):
        return snapshot_main(["--rebuild", str(args.rebuild)])
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


def cmd_eval_capture(args: argparse.Namespace) -> int:
    """Convert a consented, redacted session into a candidate item.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; ``args.capture_args`` pass through to
        ``evals/dataset/capture.py`` unchanged.

    Returns
    -------
    int
        Exit code from ``capture.main``.
    """
    try:
        from evals.dataset.capture import main as capture_main
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc
    return capture_main(list(args.capture_args))


def cmd_eval_dataset(args: argparse.Namespace) -> int:
    """Run a dataset tooling command (``ember eval dataset <subcommand>``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; ``args.dataset_command`` selects the module and the
        remaining flags are forwarded to its ``main``.

    Returns
    -------
    int
        Exit code from the module's ``main``.
    """
    try:
        from evals.dataset import card, check, hashes, lint, stability, tiers
    except ImportError as exc:
        raise RuntimeError(_EVAL_CHECKOUT_ERROR) from exc
    modules = {
        "lint": lint.main,
        "card": card.main,
        "hash": hashes.main,
        "check": check.main,
        "tier": tiers.main,
        "stability": stability.main,
    }
    argv: list[str] = []
    if getattr(args, "benchmark_dir", None):
        argv += ["--from", str(args.benchmark_dir)]
    if getattr(args, "dataset", None):
        argv += ["--dataset", str(args.dataset)]
    if getattr(args, "enforce_all", False):
        argv.append("--enforce-all")
    if getattr(args, "as_json", False):
        argv.append("--json")
    if getattr(args, "check", False):
        argv.append("--check")
    if getattr(args, "emit", False):
        argv.append("--emit")
    if getattr(args, "ingest", None):
        argv += ["--ingest", str(args.ingest)]
    if getattr(args, "report", False):
        argv.append("--report")
    if getattr(args, "round_id", None):
        argv += ["--round", str(args.round_id)]
    if getattr(args, "rounds_dir", None):
        argv += ["--rounds-dir", str(args.rounds_dir)]
    if getattr(args, "out", None):
        argv += ["--out", str(args.out)]
    return modules[args.dataset_command](argv)
