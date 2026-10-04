#!/usr/bin/env python3
"""Render ember benchmark results as Markdown.

Usage
-----
    python evals/eval/report_evals.py                     # most recent run
    python evals/eval/report_evals.py results/<run>_results.json
    python evals/eval/report_evals.py --format json results/<run>_results.json
    python evals/eval/report_evals.py --compare \
        results/<a>_results.json results/<b>_results.json
    python evals/eval/report_evals.py --export [results/<run>_results.json] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from evals.export import export  # noqa: E402

RESULTS_DIR = REPO_ROOT / "results"
DASH = "—"


def _pct(value: float | None) -> str:
    return DASH if value is None else f"{value * 100:.1f}%"


def _num(value: float | None) -> str:
    return DASH if value is None else f"{value:.3f}"


def _ci(interval: list[float] | None) -> str:
    if not interval:
        return DASH
    return f"[{interval[0] * 100:.1f}, {interval[1] * 100:.1f}]"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    widths = [
        max([len(h), *(len(row[i]) for row in rows)]) for i, h in enumerate(headers)
    ]

    def line(cells: list[str]) -> str:
        padded = (cell.ljust(width) for cell, width in zip(cells, widths, strict=True))
        return "| " + " | ".join(padded) + " |"

    rule = "| " + " | ".join("-" * width for width in widths) + " |"
    return [line(headers), rule, *(line(row) for row in rows), ""]


def render(data: dict[str, Any]) -> str:
    """One run's summary as Markdown."""
    cfg = data["config"]
    summary = data["summary"]
    overall = summary["overall"]
    choice, noul, score = summary["choice"], summary["noul"], summary["score"]

    out = [f"## ember benchmark: {cfg['run_id']}", ""]
    meta = (
        f"model `{cfg['model']}` · git `{cfg['git_hash']}` · dataset "
        f"`{cfg['dataset']}` (`{cfg['dataset_sha256'][:12]}`) · split "
        f"{cfg['split'] or 'all'} · {cfg['n_items']} items"
    )
    if cfg["n_errors"]:
        meta += f" · {cfg['n_errors']} errors"
    out += [meta, ""]
    out += [
        f"**Question accuracy {_pct(overall['accuracy'])}** "
        f"{_ci(overall['accuracy_ci'])} over {overall['questions']} questions · "
        f"items fully correct {_pct(overall['item_accuracy'])} of {overall['items']}",
        "",
    ]

    rows = []
    if choice:
        rows.append(
            [
                "choice",
                str(choice["n"]),
                _pct(choice["accuracy"]),
                _ci(choice["accuracy_ci"]),
                _num(choice["macro_f1"]),
                _num(choice["ece"]),
                _num(choice["brier"]),
                DASH,
                DASH,
            ]
        )
    if noul:
        rows.append(
            [
                "noul",
                str(noul["n"]),
                _pct(noul["accuracy"]),
                _ci(noul["accuracy_ci"]),
                DASH,
                _num(noul["ece"]),
                _num(noul["brier"]),
                DASH,
                DASH,
            ]
        )
    if score:
        rows.append(
            [
                "score",
                str(score["n"]),
                _pct(score["accuracy"]),
                _ci(score["accuracy_ci"]),
                DASH,
                DASH,
                DASH,
                _num(score["rps"]),
                _num(score["mae"]),
            ]
        )
    out += ["### By question type", ""]
    out += _table(
        [
            "Type",
            "N",
            "Accuracy ↑",
            "95% CI",
            "Macro-F1 ↑",
            "ECE ↓",
            "Brier ↓",
            "RPS ↓",
            "MAE ↓",
        ],
        rows,
    )
    if score:
        out += [
            "A score answer counts as correct when its expected score rounds to the "
            f"gold level; {_pct(score['within_one'])} are within one level.",
            "",
        ]

    rows = []
    if choice:
        acting = choice["acting"]
        rows.append(
            [
                "choice",
                "confidence ≥ 0.85",
                _pct(acting["coverage"]),
                _pct(acting["accuracy"]),
            ]
        )
    if noul:
        acting = noul["acting"]
        rows.append(
            [
                "noul",
                "P ≥ 0.80 or P ≤ 0.20",
                _pct(acting["coverage"]),
                _pct(acting["accuracy"]),
            ]
        )
    if rows:
        out += ["### At the agent-kit thresholds", ""]
        out += _table(
            ["Answer", "Agent acts when", "Coverage", "Accuracy when acting"], rows
        )

    rows = [
        [
            qid,
            q["category"],
            q["type"],
            str(q["n"]),
            _pct(q["accuracy"]),
            _num(q.get("brier", q.get("rps"))),
            _num(q.get("mae")),
        ]
        for qid, q in summary["questions"].items()
    ]
    out += ["### By question", ""]
    out += _table(
        ["Question", "Recipe", "Type", "N", "Accuracy ↑", "Brier / RPS ↓", "MAE ↓"],
        rows,
    )

    rows = [
        [category, str(c["items"]), _pct(c["item_accuracy"]), _pct(c["accuracy"])]
        for category, c in summary["categories"].items()
    ]
    out += ["### By recipe", ""]
    out += _table(
        ["Recipe", "Items", "Items fully correct ↑", "Question accuracy ↑"], rows
    )

    out += ["### Reliability (top-label confidence)", ""]
    for name, part in (("choice", choice), ("noul", noul)):
        if part:
            rows = [
                [
                    f"{b['low']:.1f}-{b['high']:.1f}",
                    str(b["n"]),
                    _num(b["confidence"]),
                    _pct(b["accuracy"]),
                ]
                for b in part["reliability"]
            ]
            out += [f"{name}:", ""]
            out += _table(["Bin", "N", "Mean confidence", "Accuracy"], rows)

    misses = summary["misses"]
    out += [f"### Misses ({len(misses)})", ""]
    if misses:
        rows = [
            [
                m["id"],
                m["question"],
                str(m["gold"]),
                str(m["predicted"]),
                _num(m["signal"]),
            ]
            for m in misses
        ]
        out += _table(
            ["Item", "Question", "Gold", "Predicted", "Confidence / P / score"], rows
        )

    latency = cfg.get("latency_ms")
    if latency:
        out.append(
            f"*Latency per request: mean {latency['mean']:.0f} ms · p50 "
            f"{latency['p50']:.0f} ms · p95 {latency['p95']:.0f} ms · max "
            f"{latency['max']:.0f} ms*"
        )
    return "\n".join(out)


def _delta(a: float | None, b: float | None, *, percent: bool) -> str:
    if a is None or b is None:
        return DASH
    return f"{(b - a) * 100:+.1f} pts" if percent else f"{b - a:+.3f}"


COMPARED = (
    ("Question accuracy ↑", "overall", "accuracy", True),
    ("Items fully correct ↑", "overall", "item_accuracy", True),
    ("choice accuracy ↑", "choice", "accuracy", True),
    ("choice ECE ↓", "choice", "ece", False),
    ("choice Brier ↓", "choice", "brier", False),
    ("noul accuracy ↑", "noul", "accuracy", True),
    ("noul ECE ↓", "noul", "ece", False),
    ("noul Brier ↓", "noul", "brier", False),
    ("score accuracy ↑", "score", "accuracy", True),
    ("score MAE ↓", "score", "mae", False),
    ("score RPS ↓", "score", "rps", False),
)


def render_compare(a: dict[str, Any], b: dict[str, Any]) -> str:
    """Two runs side by side, B minus A."""
    cfg_a, cfg_b = a["config"], b["config"]
    sum_a, sum_b = a["summary"], b["summary"]
    out = [
        "## ember benchmark: comparison",
        "",
        f"A `{cfg_a['run_id']}` (git `{cfg_a['git_hash']}`) · "
        f"B `{cfg_b['run_id']}` (git `{cfg_b['git_hash']}`)",
        "",
    ]
    if any(
        cfg_a.get(k) != cfg_b.get(k) for k in ("dataset_sha256", "split", "category")
    ):
        out += [
            "**Warning:** the runs scored different item sets (dataset, split, or "
            "category differs), so these deltas are not comparable.",
            "",
        ]
    rows = []
    for label, section, key, percent in COMPARED:
        value_a = (sum_a.get(section) or {}).get(key)
        value_b = (sum_b.get(section) or {}).get(key)
        fmt = _pct if percent else _num
        rows.append(
            [
                label,
                fmt(value_a),
                fmt(value_b),
                _delta(value_a, value_b, percent=percent),
            ]
        )
    for qid in dict.fromkeys([*sum_a["questions"], *sum_b["questions"]]):
        value_a = sum_a["questions"].get(qid, {}).get("accuracy")
        value_b = sum_b["questions"].get(qid, {}).get("accuracy")
        rows.append(
            [
                f"{qid} accuracy ↑",
                _pct(value_a),
                _pct(value_b),
                _delta(value_a, value_b, percent=True),
            ]
        )
    out += _table(["Metric", "A", "B", "Δ (B-A)"], rows)
    return "\n".join(out)


def _read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        print(f"error: results file not found: {path}", file=sys.stderr)
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if "overall" not in data.get("summary", {}):
        print(
            f"error: {path.name} predates the current results format; "
            "re-run: ember eval run",
            file=sys.stderr,
        )
        return None
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="report_evals", description="Render ember benchmark results."
    )
    parser.add_argument("results_file", type=Path, nargs="?", help="a *_results.json")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument(
        "--compare",
        nargs=2,
        type=Path,
        metavar=("RUN_A", "RUN_B"),
        help="compare two results files",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="write the reviewer bundle: report.md, report.html, figures, data",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="bundle directory for --export"
    )
    parser.add_argument(
        "--agent",
        default=None,
        help="with --export: attach an agent_*_results.json run, or 'latest'",
    )
    return parser


def _latest_agent() -> Path | None:
    candidates = list(RESULTS_DIR.glob("agent_*_results.json"))
    if not candidates:
        print(
            "error: no agent runs in results/; run: ember eval agent", file=sys.stderr
        )
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _latest() -> Path | None:
    candidates = [
        p for p in RESULTS_DIR.glob("*_results.json") if not p.name.startswith("agent_")
    ]
    if not candidates:
        print("error: no results in results/; run: ember eval run", file=sys.stderr)
        return None
    path = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"# most recent run: {path.name}\n", file=sys.stderr)
    return path


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.compare:
        runs = [_read(path) for path in args.compare]
        if runs[0] is None or runs[1] is None:
            return 1
        print(render_compare(runs[0], runs[1]))
        return 0

    path = args.results_file or _latest()
    if path is None:
        return 1
    data = _read(path)
    if data is None:
        return 1
    if args.export:
        agent = None
        if args.agent:
            agent = _latest_agent() if args.agent == "latest" else Path(args.agent)
            if agent is None or not agent.exists():
                print(f"error: agent results not found: {args.agent}", file=sys.stderr)
                return 1
        bundle = export(path, args.out, agent)
        print(f"report bundle: {bundle}")
        for name in ("report.html", "report.md", "figures/", "data/"):
            print(f"  {bundle / name}")
        return 0
    print(json.dumps(data, indent=2) if args.format == "json" else render(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
