#!/usr/bin/env python3
"""Snapshot a benchmark run into the tracked ``benchmark/<run-id>/`` bundle.

This is everything up to (but not including) HTML rendering: the run's results,
trace, and scored dataset, plus the report **model** that ``analysis.build``
computes. The website build (``scripts/build_site_benchmark.py``) renders the
model into pages, so this bundle is the data the site serves.

Usage
-----
    python3 scripts/snapshot_evals.py                  # most recent run
    python3 scripts/snapshot_evals.py results/<run>_results.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from evals import analysis  # noqa: E402

RESULTS_DIR = REPO / "results"
BENCHMARK_DIR = REPO / "benchmark"


def _latest() -> Path | None:
    candidates = [
        p for p in RESULTS_DIR.glob("*_results.json") if not p.name.startswith("agent_")
    ]
    if not candidates:
        print("error: no results in results/; run: ember eval run", file=sys.stderr)
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def snapshot(results_path: Path) -> Path:
    """Write the tracked bundle for ``results_path`` and return its directory."""
    model = analysis.build(results_path)
    meta = model["meta"]
    run_id = meta["run_id"]
    out = BENCHMARK_DIR / run_id
    out.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(results_path, out / "results.json")
    shutil.copyfile(results_path.with_name(meta["trace_file"]), out / "trace.jsonl")
    dataset = analysis.dataset_for(results_path, meta["dataset"])
    if dataset.exists():
        shutil.copyfile(dataset, out / "dataset.jsonl")
    (out / "model.json").write_text(
        json.dumps(model, indent=2) + "\n", encoding="utf-8"
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="snapshot_evals")
    parser.add_argument("results_file", type=Path, nargs="?")
    args = parser.parse_args(argv)
    path = args.results_file or _latest()
    if path is None:
        return 1
    if not path.exists():
        print(f"error: results file not found: {path}", file=sys.stderr)
        return 1
    out = snapshot(path)
    print(f"snapshot: {out}")
    for name in sorted(p.name for p in out.iterdir()):
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
