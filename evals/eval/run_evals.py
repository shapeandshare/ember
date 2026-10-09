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
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ember import models  # noqa: E402
from ember.cfg.endpoint import (  # noqa: E402
    Endpoint,
    InsecureEndpointError,
    InvalidEndpointError,
    build_auth_headers,
)

from evals.export import write_atomic  # noqa: E402
from evals.metrics import aggregate, score_item  # noqa: E402

DATASET_PATH = REPO_ROOT / "evals" / "clef-flash.jsonl"
RESULTS_DIR = REPO_ROOT / "results"
DEFAULT_SERVER = "http://127.0.0.1:8765"
TIMEOUT = 120.0
PACKAGES = ("ember-advise", "torch", "transformers", "mcp")


def _resolve_server(flag: str | None) -> str:
    """Resolve the server URL: an explicit flag, else the configured endpoint.

    Parameters
    ----------
    flag : str | None
        The ``--server`` value, or ``None`` when unset.

    Returns
    -------
    str
        The flag when given; otherwise the endpoint resolved through
        ``Endpoint.resolve`` (env > config file > default), falling back to the
        loopback default when the configured endpoint is invalid or insecure.
    """
    if flag:
        return flag
    try:
        return Endpoint.resolve().url
    except (InvalidEndpointError, InsecureEndpointError):
        return DEFAULT_SERVER


def _git_hash() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.strip()


def _cpu() -> str:
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],  # noqa: S607
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return platform.processor() or "unknown"
    return out.strip()


def _host() -> dict[str, Any]:
    packages: dict[str, str] = {}
    for name in PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return {
        "platform": platform.platform(),
        "cpu": _cpu(),
        "python": platform.python_version(),
        "packages": packages,
    }


def _model_spec(model_dir: str) -> dict[str, str]:
    """The pinned registry entry a model directory belongs to, if any."""
    name = Path(model_dir).name
    for spec in models.REGISTRY.values():
        if name in (spec.dir_name, spec.revision):
            return {
                "name": spec.name,
                "repo": spec.repo,
                "params": spec.params,
                "revision": spec.revision,
            }
    return {}


def _engine(server: str) -> dict[str, Any]:
    try:
        engine = httpx.get(f"{server}/health", timeout=5.0).json().get("engine")
    except (httpx.HTTPError, ValueError):
        return {}
    return engine if isinstance(engine, dict) else {}


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


def _advise(server: str, item: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": "clef-flash",
        "state": item["state"],
        "questions": item["questions"],
    }
    for key in ("images", "videos", "media_kwargs"):
        if item.get(key) is not None:
            payload[key] = item[key]
    response = httpx.post(
        f"{server}/v1/systemone",
        json=payload,
        timeout=TIMEOUT,
        headers=build_auth_headers(),
    )
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return body


def _latency(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "mean": round(sum(ordered) / len(ordered), 1),
        "p50": round(ordered[(len(ordered) - 1) // 2], 1),
        "p95": round(ordered[int(0.95 * (len(ordered) - 1))], 1),
        "max": round(ordered[-1], 1),
    }


def run_evals(
    server: str,
    *,
    split: str | None = None,
    category: str | None = None,
    dry_run: bool = False,
    dataset_path: Path = DATASET_PATH,
) -> int:
    """Score the dataset against ``server``; return a process exit code."""
    if not dataset_path.exists():
        print(f"error: dataset not found at {dataset_path}", file=sys.stderr)
        return 1
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

    engine = _engine(server)
    model = Path(str(engine.get("model_dir", "unknown"))).name
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{model}_{timestamp}"
    RESULTS_DIR.mkdir(exist_ok=True)
    trace_path = RESULTS_DIR / f"{run_id}_trace.jsonl"
    results_path = RESULTS_DIR / f"{run_id}_results.json"
    dataset_snapshot = RESULTS_DIR / f"{run_id}_dataset.jsonl"
    shutil.copyfile(dataset_path, dataset_snapshot)

    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    with trace_path.open("w", encoding="utf-8") as trace:
        for index, item in enumerate(items, 1):
            prefix = f"  [{index:>3}/{len(items)}] {item['id']:<12}"
            started = time.monotonic()
            try:
                body = _advise(server, item)
                scored = score_item(item, body.get("answers", {}))
            except (httpx.HTTPError, ValueError) as exc:
                errors += 1
                print(f"{prefix} ERROR {exc}", file=sys.stderr)
                continue
            elapsed = (time.monotonic() - started) * 1000
            latencies.append(elapsed)
            scored.update(
                latency_ms=round(elapsed, 1),
                model=body.get("model"),
                usage=body.get("usage", {}),
                answers=body.get("answers", {}),
            )
            results.append(scored)
            trace.write(json.dumps(scored) + "\n")
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
        "timestamp": timestamp,
        "git_hash": _git_hash(),
        "model": model,
        "model_spec": _model_spec(str(engine.get("model_dir", ""))),
        "engine": engine,
        "host": _host(),
        "server": server,
        "dataset": dataset_path.name,
        "dataset_file": dataset_snapshot.name,
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "trace": trace_path.name,
        "split": split,
        "category": category,
        "n_items": len(items),
        "n_errors": errors,
        "latency_ms": _latency(latencies),
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return run_evals(
        _resolve_server(args.server),
        split=args.split,
        category=args.category,
        dry_run=args.dry_run,
        dataset_path=args.dataset,
    )


if __name__ == "__main__":
    raise SystemExit(main())
