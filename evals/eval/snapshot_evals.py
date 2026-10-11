#!/usr/bin/env python3
"""Snapshot a benchmark run into the tracked ``benchmark/<run-id>/`` bundle.

This is everything up to (but not including) HTML rendering: the run's results,
trace, and scored dataset, plus the report **model** that ``analysis.build``
computes. The website build (``scripts/build_site_benchmark.py``) renders the
model into pages, so this bundle is the data the site serves.

Usage
-----
    python3 evals/eval/snapshot_evals.py                  # most recent run
    python3 evals/eval/snapshot_evals.py results/<run>_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evals import analysis  # noqa: E402
from evals.atomic import copy_atomic, write_atomic  # noqa: E402
from evals.dataset import hashes  # noqa: E402
from evals.dataset import io as dataset_io  # noqa: E402
from evals.eval import resume  # noqa: E402
from evals.metrics import aggregate  # noqa: E402

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


_CONFIG_LOCATION_KEYS = ("server",)
_ENGINE_LOCATION_KEYS = ("model", "model_dir")


def _public_results(results_path: Path) -> dict:
    """Return ``results_path``'s contents with sensitive location fields removed.

    The raw ``results/*_results.json`` a benchmark run writes locally is not
    meant to be published as-is: ``config.server`` can be a real deployment
    URL, and ``config.engine.model``/``model_dir`` can be a real S3 bucket
    path or a local filesystem path carrying the operator's username. This
    mirrors ``evals.analysis.build``'s scrubbing of the same fields when it
    builds the published report model — this function applies the same rule
    to the raw results file this script copies into the tracked bundle,
    which would otherwise re-leak what ``model.json`` already strips (see
    vault/decisions/2026-10-10-generic-deployment-labels.md).

    Parameters
    ----------
    results_path : Path
        Path to the run's ``*_results.json``.

    Returns
    -------
    dict
        The parsed results with ``_CONFIG_LOCATION_KEYS`` removed from
        ``config`` and ``_ENGINE_LOCATION_KEYS`` removed from
        ``config.engine``.
    """
    raw = json.loads(results_path.read_text(encoding="utf-8"))
    config = {k: v for k, v in raw["config"].items() if k not in _CONFIG_LOCATION_KEYS}
    config["engine"] = {
        k: v
        for k, v in (config.get("engine") or {}).items()
        if k not in _ENGINE_LOCATION_KEYS
    }
    return {**raw, "config": config}


def snapshot(results_path: Path) -> Path:
    """Write the tracked bundle for ``results_path`` and return its directory."""
    model = analysis.build(results_path)
    meta = model["meta"]
    run_id = meta["run_id"]
    out = BENCHMARK_DIR / str(run_id)
    out.mkdir(parents=True, exist_ok=True)

    public_results = _public_results(results_path)
    write_atomic(out / "results.json", json.dumps(public_results, indent=2) + "\n")
    copy_atomic(results_path.with_name(meta["trace_file"]), out / "trace.jsonl")
    dataset = analysis.dataset_for(results_path, meta["dataset"])
    if dataset.exists():
        copy_atomic(dataset, out / "dataset.jsonl")
    write_atomic(out / "model.json", json.dumps(model, indent=2) + "\n")
    return out


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def rebuild(run_id: str) -> Path | None:
    """Recompute a tracked bundle's summary and model from its own trace and dataset.

    The bundle's ``dataset.jsonl`` may still carry pre-Phase-0 string sources,
    so it is read through the legacy shim with the bundle's own file hash as the
    legacy ``dataset_version``; trace rows gain the item annotations joined by
    id; ``config`` gains the content, per-recipe, and register hashes (the
    register hash is ``null`` for a run that predates the register).

    Parameters
    ----------
    run_id : str
        The bundle directory name under ``benchmark/``.

    Returns
    -------
    Path | None
        The bundle, or ``None`` when ``trace.jsonl`` or ``dataset.jsonl`` is missing.
    """
    bundle = BENCHMARK_DIR / run_id
    trace_path, dataset_path = bundle / "trace.jsonl", bundle / "dataset.jsonl"
    results_path = bundle / "results.json"
    if not (trace_path.exists() and dataset_path.exists() and results_path.exists()):
        print(
            f"error: {bundle} lacks trace.jsonl, dataset.jsonl, or results.json",
            file=sys.stderr,
        )
        return None
    stored = json.loads(results_path.read_text(encoding="utf-8"))
    config = dict(stored["config"])
    items = dataset_io.read_items(
        dataset_path, legacy_dataset_version=str(config["dataset_sha256"])
    )
    by_id = {item.id: item for item in items}
    rows = []
    for row in _rows(trace_path):
        item = by_id.get(str(row["id"]))
        if item is not None:
            source = item.source
            row.update(
                kind=item.kind.value if item.kind else None,
                tier=item.tier,
                source_kind=source.kind.value,
                parent_id=source.parent_id,
                perturbation=source.perturbation,
            )
        rows.append(row)
    write_atomic(trace_path, "".join(json.dumps(r) + "\n" for r in rows))
    config.setdefault("dataset_content_sha256", hashes.dataset_content_sha256(items))
    config.setdefault("recipe_sha256", hashes.recipe_hashes(items))
    config.setdefault("register_sha256", None)
    config.setdefault("settings", resume.settings_from(config.get("engine") or {}))
    config.setdefault("dataset_file", "dataset.jsonl")
    config["trace"] = "trace.jsonl"
    public = {**stored, "config": config, "summary": aggregate(rows)}
    write_atomic(results_path, json.dumps(public, indent=2) + "\n")
    model = analysis.build(results_path, dataset_path=dataset_path)
    write_atomic(bundle / "model.json", json.dumps(model, indent=2) + "\n")
    return bundle


def main(argv: list[str] | None = None) -> int:
    """Snapshot a run, or ``--rebuild`` a tracked bundle in place."""
    parser = argparse.ArgumentParser(prog="snapshot_evals")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("results_file", type=Path, nargs="?")
    group.add_argument("--rebuild", metavar="RUN_ID", default=None)
    args = parser.parse_args(argv)
    if args.rebuild:
        out = rebuild(args.rebuild)
        if out is None:
            return 1
        print(f"rebuilt: {out}")
        return 0
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
