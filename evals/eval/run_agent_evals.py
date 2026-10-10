#!/usr/bin/env python3
"""Run the agent-in-the-loop eval: opencode on scripted scenarios, scored.

Every session runs ``opencode run --pure`` in a fresh sandbox (temporary git repo
plus a private HOME and XDG dirs), so the user's opencode config, plugins,
sessions, and running instances are untouched. This runner is opt-in and never
part of ``make check`` or ``make test`` (constitution Article IV).

Usage
-----
    python evals/eval/run_agent_evals.py                       # full matrix
    python evals/eval/run_agent_evals.py --smoke                # 1 trial, 6 scenarios
    python evals/eval/run_agent_evals.py --models openrouter/anthropic/claude-sonnet-5 \
        --conditions none full --trials 3 --scenarios change_risk
    python evals/eval/run_agent_evals.py --report results/agent_<ts>_results.json

Writes ``results/agent_<timestamp>_trace.jsonl`` and ``..._results.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from evals.agent import judge, opencode, sandbox, summary  # noqa: E402
from evals.agent.condition import Condition  # noqa: E402
from evals.agent.scenarios import SCENARIOS  # noqa: E402
from evals.export import write_atomic  # noqa: E402

from .provenance import git_hash, host_info  # noqa: E402
from .run_evals import _resolve_server  # noqa: E402

RESULTS_DIR = REPO_ROOT / "results"
DEFAULT_MODELS = (
    "openrouter/deepseek/deepseek-v4.1-flash",
    "openrouter/anthropic/claude-sonnet-5",
)
SMOKE = (
    "ready_vague_thing",
    "ready_precise_version",
    "fail_logic_add",
    "risk_auth_localhost",
    "route_storage",
    "control_read",
)
EMBER_MCP = REPO_ROOT / ".venv" / "bin" / "ember-mcp"


def _select(names: list[str] | None, smoke: bool) -> list[dict[str, Any]]:
    if smoke and not names:
        names = list(SMOKE)
    if not names:
        return list(SCENARIOS)
    wanted = set(names)
    chosen = [s for s in SCENARIOS if s["id"] in wanted or s["recipe"] in wanted]
    if not chosen:
        raise SystemExit(f"error: no scenarios match {sorted(wanted)}")
    return chosen


def _preflight(server: str, models: list[str], conditions: list[str]) -> dict[str, Any]:
    keys: dict[str, str] = {}
    for model in models:
        keys.update(opencode.provider_env(model))
    engine: dict[str, Any] = {}
    if any(c != Condition.NONE for c in conditions):
        try:
            engine = httpx.get(f"{server}/health", timeout=5).json().get("engine") or {}
        except httpx.HTTPError as exc:
            raise SystemExit(
                f"error: ember is not reachable at {server}; run: ember start"
            ) from exc
        if not EMBER_MCP.exists():
            raise SystemExit(f"error: {EMBER_MCP} missing; run: make sync")
    executable = opencode.binary()
    version = subprocess.run(  # noqa: S603 - the resolved opencode binary
        [executable, "--version"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return {"keys": keys, "engine": engine, "binary": executable, "version": version}


def _session(
    job: dict[str, Any],
    ready: dict[str, Any],
    server: str,
    timeout: float,
    keep: bool,
    retries: int,
) -> dict[str, Any]:
    attempt = 0
    while True:
        record = _attempt(job, ready, server, timeout, keep)
        attempt += 1
        if (
            attempt > retries
            or record["valid"]
            or not opencode.transient(record["errors"], record["stderr"])
        ):
            record["attempts"] = attempt
            return record
        time.sleep(30 * attempt)


def _attempt(
    job: dict[str, Any], ready: dict[str, Any], server: str, timeout: float, keep: bool
) -> dict[str, Any]:
    scenario = job["scenario"]
    box = sandbox.create(
        scenario, job["condition"], ember_mcp=[str(EMBER_MCP)], server_url=server
    )
    try:
        before = sandbox.snapshot(box)
        env = opencode.environment(box, {k: v for k, v in ready["keys"].items()})
        argv = opencode.command(
            ready["binary"],
            job["model"],
            box,
            scenario["prompt"],
            f"ember-eval {scenario['id']}",
        )
        transcript = opencode.run(argv, env, box.repo, timeout)
        after = sandbox.snapshot(box)
        run = {
            "model": job["model"],
            "condition": job["condition"],
            "trial": job["trial"],
        }
        record = judge.score(scenario, run, transcript, box, before, after)
        record["sandbox"] = str(box.root) if keep else None
        return record
    finally:
        if not keep:
            sandbox.remove(box)


def _pct(entry: dict[str, Any] | None) -> str:
    if not entry:
        return "  n/a "
    return f"{entry['rate'] * 100:5.1f}%"


def render(results: dict[str, Any]) -> str:
    """Return a terminal report for an agent-eval results file."""
    config, result = results["config"], results["summary"]
    lines = [
        f"agent eval {config['run_id']}  opencode {config['opencode']}  "
        f"{result['valid']}/{result['runs']} valid sessions",
        "",
        f"{'model':<34} {'condition':<9} {'n':>3}  {'action':>7} {'consult':>8} "
        f"{'before':>7} {'recipe':>7} {'follow':>7} {'cq':>6} "
        f"{'cq_vf':>6} {'cq_id':>6} {'over':>6} {'$/run':>7} {'s/run':>6}",
    ]
    for g in result["groups"]:
        lines.append(
            f"{g['model'].split('/')[-1]:<34} {g['condition']:<9} {g['runs']:>3}  "
            f"{_pct(g['action']):>7} {_pct(g['consult']):>8} "
            f"{_pct(g['before_act']):>7} "
            f"{_pct(g['recipe_fidelity']):>7} {_pct(g['followed']):>7} "
            f"{f'{g.get("call_quality", 0) or 0:.2f}':>6} "
            f"{_pct(g.get('cq_verdict_free')):>6} {_pct(g.get('cq_ids_correct')):>6} "
            f"{_pct(g['over_consult']):>6} {g['cost'] or 0:7.4f} "
            f"{g['seconds'] or 0:6.0f}"
        )
    lat = result.get("latency_by_recipe")
    if lat:
        lines += ["", "latency and ember overhead by recipe:"]
        for recipe, v in sorted(lat.items()):
            we = v.get("with_ember_s")
            ne = v.get("without_ember_s")
            ov = v.get("overhead_s")
            pc = v.get("per_call_ms")
            we_s = f"{we:.1f}s" if we else " n/a "
            ne_s = f"{ne:.1f}s" if ne else " n/a "
            ov_s = f"+{ov:.1f}s" if ov else "  n/a  "
            pc_s = f"{pc:.0f}ms" if pc else " n/a"
            lines.append(
                f"  {recipe:<18} with={we_s}  no={ne_s}  overhead={ov_s}  call={pc_s}"
            )
    if result["deltas"]:
        lines += [
            "",
            "gold-action accuracy vs no ember (paired by scenario and trial):",
        ]
        for d in result["deltas"]:
            low, high = d["ci"]
            lines.append(
                f"  {d['model'].split('/')[-1]:<32} {d['condition']:<6} "
                f"{d['delta'] * 100:+6.1f} pts  [{low * 100:+.1f}, "
                f"{high * 100:+.1f}]  n={d['n']}"
            )
    if result["invalid"]:
        lines += ["", f"{len(result['invalid'])} invalid sessions (excluded):"]
        lines += [
            f"  {i['model'].split('/')[-1]} {i['condition']} {i['scenario']} "
            f"t{i['trial']} timeout={i['timed_out']} exit={i['exit_code']}"
            for i in result["invalid"][:10]
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run (or report on) the agent eval; return an exit code."""
    args = _parser().parse_args(argv)
    args.server = _resolve_server(args.server)
    if args.report:
        print(render(json.loads(Path(args.report).read_text(encoding="utf-8"))))
        return 0
    carried: list[dict[str, Any]] = []
    resumed_from = None
    if args.resume:
        previous = json.loads(Path(args.resume).read_text(encoding="utf-8"))["config"]
        old_trace = Path(args.resume).with_name(previous["trace"])
        lines = old_trace.read_text(encoding="utf-8").splitlines()
        carried = [r for r in map(json.loads, filter(None, lines)) if r["valid"]]
        args.models, args.conditions = previous["models"], previous["conditions"]
        wanted = set(previous["scenarios"])
        scenarios = [s for s in SCENARIOS if s["id"] in wanted]
        snapshot = previous.get("scenarios_snapshot")
        if snapshot:
            current = {s["id"]: s for s in SCENARIOS}
            changed = [
                s["id"]
                for s in snapshot
                if s["id"] not in current
                or current[s["id"]]["prompt"] != s["prompt"]
                or current[s["id"]]["gold_action"] != s["gold_action"]
            ]
            if changed:
                raise SystemExit(
                    "error: scenarios changed since the run being resumed: "
                    + ", ".join(changed)
                )
        trials, resumed_from = previous["trials"], previous["run_id"]
    else:
        scenarios = _select(args.scenarios, args.smoke)
        trials = 1 if args.smoke and args.trials is None else (args.trials or 2)
    ready = _preflight(args.server, args.models, args.conditions)
    done_keys = {
        (r["scenario"], r["condition"], r["model"], r["trial"]) for r in carried
    }
    jobs = [
        {"scenario": s, "condition": c, "model": m, "trial": t}
        for t in range(1, trials + 1)
        for m in args.models
        for c in args.conditions
        for s in scenarios
        if (s["id"], c, m, t) not in done_keys
    ]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"agent_{stamp}"
    RESULTS_DIR.mkdir(exist_ok=True)
    trace_path = RESULTS_DIR / f"{run_id}_trace.jsonl"
    print(
        f"agent eval {run_id}: {len(jobs)} sessions ({len(scenarios)} scenarios x "
        f"{len(args.conditions)} conditions x {len(args.models)} models x {trials} "
        f"trials), {args.parallel} at a time"
        + (
            f"; {len(carried)} valid sessions carried over from {resumed_from}"
            if resumed_from
            else ""
        )
    )
    records: list[dict[str, Any]] = list(carried)
    lock = threading.Lock()
    with (
        trace_path.open("w", encoding="utf-8") as trace,
        ThreadPoolExecutor(max_workers=args.parallel) as pool,
    ):
        trace.writelines(json.dumps(record) + "\n" for record in carried)
        futures = [
            pool.submit(
                _session, job, ready, args.server, args.timeout, args.keep, args.retries
            )
            for job in jobs
        ]
        for done, future in enumerate(as_completed(futures), 1):
            record = future.result()
            with lock:
                records.append(record)
                trace.write(json.dumps(record) + "\n")
                trace.flush()
            mark = (
                "ok  "
                if record["action_ok"]
                else ("ERR " if not record["valid"] else "miss")
            )
            print(
                f"  [{done:>4}/{len(jobs)}] {mark} {record['model'].split('/')[-1]:<24}"
                f" {record['condition']:<6} {record['scenario']:<24} "
                f"ember={'yes' if record['consulted'] else 'no '} "
                f"{record['seconds']:>5.0f}s ${record['cost']:.4f}",
                flush=True,
            )
    scenario_snapshot = [
        {
            "id": s["id"],
            "recipe": s["recipe"],
            "gold_action": s["gold_action"],
            "rationale": s["rationale"],
            "prompt": s["prompt"],
        }
        for s in scenarios
    ]
    config = {
        "run_id": run_id,
        "timestamp": stamp,
        "git_hash": git_hash(),
        "opencode": ready["version"],
        "engine": ready["engine"],
        "host": host_info(),
        "server": args.server,
        "models": args.models,
        "conditions": args.conditions,
        "condition_labels": {c: sandbox.CONDITION_LABELS[c] for c in args.conditions},
        "trials": trials,
        "scenarios": [s["id"] for s in scenarios],
        "scenarios_snapshot": scenario_snapshot,
        "scenario_hash": hashlib.sha256(
            json.dumps(scenario_snapshot, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest(),
        "parallel": args.parallel,
        "timeout": args.timeout,
        "trace": trace_path.name,
        "resumed_from": resumed_from,
        "carried_over": len(carried),
    }
    results = {"config": config, "summary": summary.summarize(records)}
    results_path = RESULTS_DIR / f"{run_id}_results.json"
    write_atomic(results_path, json.dumps(results, indent=2) + "\n")
    print("\n" + render(results))
    print(f"\n  trace   {trace_path}\n  results {results_path}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_agent_evals", description="Agent-in-the-loop eval via opencode."
    )
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=list(sandbox.CONDITIONS),
        choices=sandbox.CONDITIONS,
    )
    parser.add_argument("--trials", type=int, default=None, help="default 2 (smoke: 1)")
    parser.add_argument(
        "--scenarios", nargs="+", default=None, help="scenario ids or recipe names"
    )
    parser.add_argument("--smoke", action="store_true", help="6 scenarios, 1 trial")
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument(
        "--timeout", type=float, default=420.0, help="seconds per session"
    )
    parser.add_argument(
        "--server", default=None, help="server URL (default: the configured endpoint)"
    )
    parser.add_argument("--keep", action="store_true", help="keep sandboxes")
    parser.add_argument("--report", default=None, help="print a results file and exit")
    parser.add_argument(
        "--resume",
        default=None,
        help="re-run only the invalid or missing sessions of an agent_*_results.json",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="retries for provider errors such as 402, 429, and 5xx (default 2)",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
