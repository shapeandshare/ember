#!/usr/bin/env python3
"""Run the ember benchmark against a live model server.

Usage
-----
    python evals/eval/run_evals.py                      # every item
    python evals/eval/run_evals.py --split test         # held-out split only
    python evals/eval/run_evals.py --category routing   # one recipe
    python evals/eval/run_evals.py --dry-run            # list items, send nothing

Writes ``results/<model>_<timestamp>_trace.jsonl`` (one scored line per item)
and ``results/<model>_<timestamp>_results.json`` (run config plus summary). It
also copies the exact dataset it scored to
``results/<model>_<timestamp>_dataset.jsonl``, so a report reflects the bytes
that were run even after the checkout's dataset changes.
Render the summary with ``evals/eval/report_evals.py`` or ``ember eval report``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.atomic import write_atomic  # noqa: E402
from evals.dataset import hashes  # noqa: E402
from evals.dataset import io as dataset_io  # noqa: E402
from evals.dataset.register import REGISTER_PATH  # noqa: E402
from evals.eval import resume as resume_module  # noqa: E402
from evals.eval.client import advise as _advise  # noqa: E402
from evals.eval.client import deployment_label as _deployment_label  # noqa: E402
from evals.eval.client import health as _health  # noqa: E402
from evals.eval.client import model_name as _model_name  # noqa: E402
from evals.eval.client import resolve_server as _resolve_server  # noqa: E402
from evals.eval.provenance import git_hash, host_info, model_spec_info  # noqa: E402
from evals.metrics import aggregate, score_item  # noqa: E402

DATASET_PATH = REPO_ROOT / "evals" / "clef-flash.jsonl"
RESULTS_DIR = REPO_ROOT / "results"


def _load(
    dataset: Path, split: str | None, category: str | None
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item: dict[str, Any] = json.loads(line)
        if split and item["split"] != split:
            continue
        if category and item["category"] != category:
            continue
        items.append(item)
    return items


def _latency(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "mean": round(sum(ordered) / len(ordered), 1),
        "p50": round(ordered[(len(ordered) - 1) // 2], 1),
        "p95": round(ordered[int(0.95 * (len(ordered) - 1))], 1),
        "max": round(ordered[-1], 1),
    }


SPLIT_KEYS = ("state_tokens", "fixed_tokens", "media_tokens")
MIN_SERVER_VERSION = "0.12.0"


def _annotations(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return the item annotations a trace row carries (specs/004 R23)."""
    source = item.get("source")
    source = source if isinstance(source, Mapping) else {}
    return {
        "kind": item.get("kind"),
        "tier": item.get("tier"),
        "source_kind": source.get("kind", "authored"),
        "parent_id": source.get("parent_id") or item.get("parent_id"),
        "perturbation": source.get("perturbation"),
    }


def _token_split(usage: Mapping[str, Any]) -> dict[str, int] | None:
    """Return ``{total, state, fixed, media}`` from ``usage``, or ``None`` if absent."""
    if not all(key in usage for key in SPLIT_KEYS):
        return None
    return {
        "total": int(usage["input_tokens"]),
        "state": int(usage["state_tokens"]),
        "fixed": int(usage["fixed_tokens"]),
        "media": int(usage["media_tokens"]),
    }


def _hashes(dataset_path: Path) -> dict[str, Any]:
    items = dataset_io.read_raw(dataset_path)
    return {
        "dataset_sha256": hashes.dataset_sha256(dataset_path),
        "dataset_content_sha256": hashes.dataset_content_sha256(items),
        "recipe_sha256": hashes.recipe_hashes(items),
        "register_sha256": (
            hashes.register_sha256(REGISTER_PATH) if REGISTER_PATH.exists() else None
        ),
    }


def _start(
    *,
    resume_id: str | None,
    model: str,
    engine: Mapping[str, Any],
    label: str,
    dataset_path: Path,
    digests: Mapping[str, Any],
    split: str | None,
    category: str | None,
) -> tuple[str, bool] | None:
    """Create or validate the run manifest; return ``(run_id, resumed)`` or ``None``."""
    RESULTS_DIR.mkdir(exist_ok=True)
    if resume_id is None:
        run_id = f"{model}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        manifest = resume_module.RunManifest(
            run_id=run_id,
            model=model,
            deployment_label=label,
            settings=resume_module.settings_from(engine),
            split=split,
            category=category,
            started_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            **digests,
        )
        resume_module.write(resume_module.manifest_path(RESULTS_DIR, run_id), manifest)
        shutil.copyfile(dataset_path, RESULTS_DIR / f"{run_id}_dataset.jsonl")
        return run_id, False
    manifest = resume_module.read(resume_module.manifest_path(RESULTS_DIR, resume_id))
    problems = resume_module.mismatches(
        manifest,
        model=model,
        engine=engine,
        dataset_content_sha256=str(digests["dataset_content_sha256"]),
        split=split,
        category=category,
    )
    if problems:
        print(f"error: cannot resume {resume_id}:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return None
    return resume_id, True


def run_evals(
    server: str,
    *,
    split: str | None = None,
    category: str | None = None,
    dry_run: bool = False,
    dataset_path: Path = DATASET_PATH,
    deployment_label: str | None = None,
    resume: str | None = None,
) -> int:
    """Score the dataset against ``server``; return a process exit code.

    Parameters
    ----------
    deployment_label : str | None, optional
        A generic description of the deployment being benchmarked, recorded
        into the run's provenance and shown on the published report and
        leaderboard instead of ``server`` (which is kept only in this run's
        private, gitignored ``results/`` trace, never published). Falls back
        to a label derived from whether ``server`` is loopback and the
        reported device when not given — see ``client.deployment_label``.
    resume : str | None, optional
        A run id whose manifest, trace, and settings this call continues.
    """
    if not dataset_path.exists():
        print(f"error: dataset not found at {dataset_path}", file=sys.stderr)
        return 1
    if resume is not None:
        # A bare `--resume RUN_ID` continues the run as it was started; an
        # explicit filter still has to match the manifest (checked in _start).
        path = resume_module.manifest_path(RESULTS_DIR, resume)
        if not path.exists():
            print(f"error: no manifest at {path}; cannot resume", file=sys.stderr)
            return 1
        manifest = resume_module.read(path)
        split, category = split or manifest.split, category or manifest.category
    items = _load(dataset_path, split, category)
    if not items:
        print(
            f"error: no items match split={split!r} category={category!r}",
            file=sys.stderr,
        )
        return 1

    print(
        f"ember benchmark  server={server}  items={len(items)}  "
        f"split={split or 'all'}  category={category or 'all'}"
    )
    if dry_run:
        for item in items:
            print(
                f"  {item['id']:<12} {item['split']:<4}  {', '.join(item['questions'])}"
            )
        print(f"dry run: {len(items)} items listed, no requests sent")
        return 0

    health = _health(server)
    engine = health.get("engine") or {}
    server_version = health.get("version")
    model = _model_name(engine)
    label = _deployment_label(deployment_label, server, engine.get("device"))
    digests = _hashes(dataset_path)
    started = _start(
        resume_id=resume,
        model=model,
        engine=engine,
        label=label,
        dataset_path=dataset_path,
        digests=digests,
        split=split,
        category=category,
    )
    if started is None:
        return 1
    run_id, resumed = started
    trace_path = RESULTS_DIR / f"{run_id}_trace.jsonl"
    results_path = RESULTS_DIR / f"{run_id}_results.json"
    results: list[dict[str, Any]] = (
        resume_module.read_rows(trace_path) if resumed else []
    )
    if resumed:
        resume_module.repair(trace_path, results)
    done = {str(r["id"]) for r in results}
    latencies: list[float] = []
    errors = 0
    with trace_path.open("a", encoding="utf-8") as trace:
        for index, item in enumerate(items, 1):
            if item["id"] in done:
                continue
            prefix = f"  [{index:>3}/{len(items)}] {item['id']:<12}"
            started_at = time.monotonic()
            try:
                body = _advise(server, item)
                scored = score_item(item, body.get("answers", {}))
            except (httpx.HTTPError, ValueError) as exc:
                errors += 1
                print(f"{prefix} ERROR {exc}", file=sys.stderr)
                continue
            tokens = _token_split(body.get("usage") or {})
            if tokens is None:
                version = server_version or "unknown"
                print(
                    f"error: the server at {label} (ember {version}) does not return "
                    f"the token split in usage; ember >= {MIN_SERVER_VERSION} is "
                    "required for the benchmark.",
                    file=sys.stderr,
                )
                return 1
            elapsed = (time.monotonic() - started_at) * 1000
            latencies.append(elapsed)
            scored.update(
                latency_ms=round(elapsed, 1),
                # The server echoes its own loaded model identity (for a hosted
                # deployment, a full S3 URI); model_name derives the short,
                # published-safe identifier so the trace never carries the location.
                model=_model_name({"model": body.get("model")}),
                usage=body.get("usage", {}),
                answers=body.get("answers", {}),
                tokens=tokens,
                **_annotations(item),
            )
            results.append(scored)
            trace.write(json.dumps(scored) + "\n")
            trace.flush()
            misses = [
                f"{qid} {q['gold']}->{q['predicted']}"
                for qid, q in scored["questions"].items()
                if not q["correct"]
            ]
            status = "miss" if misses else "ok  "
            print(f"{prefix} {status} {elapsed:5.0f} ms  {'; '.join(misses)}")

    if not results:
        print("error: every request failed; is the server up?", file=sys.stderr)
        return 1

    summary = aggregate(results)
    config = {
        "run_id": run_id,
        "timestamp": run_id.rsplit("_", 1)[-1],
        "git_hash": git_hash(),
        "model": model,
        "model_spec": model_spec_info(model),
        "engine": engine,
        "settings": resume_module.settings_from(engine),
        "server_version": server_version,
        "host": host_info(),
        # server is kept only for this run's own debugging — it lives in the
        # private, gitignored results/ directory and is never read by
        # analysis.build(), which publishes deployment_label instead (see
        # vault/decisions/2026-10-10-generic-deployment-labels.md).
        "server": server,
        "deployment_label": label,
        "dataset": dataset_path.name,
        "dataset_file": f"{run_id}_dataset.jsonl",
        **digests,
        "trace": trace_path.name,
        "split": split,
        "category": category,
        "policy": {},
        "resumed": resumed,
        "n_items": len(items),
        "n_errors": errors,
        "latency_ms": _latency(latencies) if latencies else {},
    }
    write_atomic(
        results_path,
        json.dumps({"config": config, "summary": summary}, indent=2) + "\n",
    )

    overall = summary["overall"]
    low, high = overall["accuracy_ci"]
    print(
        f"\nquestion accuracy {overall['accuracy']:.1%} [{low:.1%}, {high:.1%}] "
        f"over {overall['questions']} questions · items fully correct "
        f"{overall['item_accuracy']:.1%} of {overall['items']} · errors {errors}"
    )
    print(f"  trace   {trace_path}")
    print(f"  results {results_path}")
    print("render it: ember eval report")
    return 0 if errors == 0 else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_evals",
        description="Run the ember benchmark against a live model server.",
    )
    parser.add_argument(
        "--server",
        default=None,
        help="model server URL (default: the configured endpoint)",
    )
    parser.add_argument("--split", choices=["dev", "test"], default=None)
    parser.add_argument("--category", default=None, help="only this recipe")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument(
        "--dry-run", action="store_true", help="list items without sending requests"
    )
    parser.add_argument(
        "--resume", default=None, metavar="RUN_ID", help="continue an interrupted run"
    )
    parser.add_argument(
        "--deployment-label",
        default=None,
        help=(
            "generic description of the deployment for the published report, "
            "e.g. 'Remote hosted (GPU, CUDA) - NVIDIA A10G, 24 GB VRAM, "
            "g5.4xlarge' (default: $EMBER_DEPLOYMENT_LABEL, or derived from "
            "whether --server is loopback plus the reported device — never "
            "the server URL itself, which is not published)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the benchmark."""
    args = _build_parser().parse_args(argv)
    return run_evals(
        _resolve_server(args.server),
        split=args.split,
        category=args.category,
        dry_run=args.dry_run,
        dataset_path=args.dataset,
        deployment_label=args.deployment_label
        or os.environ.get("EMBER_DEPLOYMENT_LABEL"),
        resume=args.resume,
    )


if __name__ == "__main__":
    raise SystemExit(main())
