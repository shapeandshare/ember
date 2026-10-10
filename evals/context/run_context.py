#!/usr/bin/env python3
"""Run the long-context probe: where does each model's quality hold? (R8-R13).

Usage
-----
    python evals/context/run_context.py              # sizing gate, then every model
    python evals/context/run_context.py --smoke      # flash, 2K and 4K, 3 items
    python evals/context/run_context.py --pilot      # stop after the sizing gate
    python evals/context/run_context.py --resume ID  # continue an interrupted run
    python evals/context/run_context.py --rescore ID # rebuild summary.json
    python evals/context/run_context.py --reproduce ID [--items N]
    python evals/context/run_context.py --snapshot ID

Writes ``results/context/<run_id>/``. Exit codes: 0 done, 1 error (including no
MPS device), 2 the sizing gate failed or a reproduction differs.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import torch  # noqa: E402
from ember import models  # noqa: E402
from ember.cfg import config  # noqa: E402
from ember.serving import process, request_size, runtime  # noqa: E402

from evals.context import items as probe_items  # noqa: E402
from evals.context import reproduce, summarize, worker  # noqa: E402
from evals.context.records.depth import Depth  # noqa: E402
from evals.context.records.probe_manifest import (  # noqa: E402
    BASELINE_LENGTH,
    EXPLORATORY_ITEMS,
    LENGTHS,
    SEED,
    ProbeManifest,
    new_run_id,
)
from evals.context.records.row_status import RowStatus  # noqa: E402
from evals.context.rows_file import read_rows  # noqa: E402
from evals.context.scoring import (  # noqa: E402
    item_scores,
    paired_deltas,
    projected_half_width,
)
from evals.export import copy_atomic, write_atomic  # noqa: E402

RESULTS_DIR = REPO_ROOT / "results" / "context"
RUNS_DIR = REPO_ROOT / "evals" / "context" / "runs"
SMOKE_LENGTHS = (2048, 4096)
SMOKE_ITEMS = 3
_GATE_LENGTH = 16384


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ember eval context",
        description="Measure accuracy, calibration, peak memory, and latency at "
        "growing request lengths, and pick each model's cap by the FR-010 rule.",
    )
    parser.add_argument(
        "--models", default=None, help="comma-separated registry models"
    )
    parser.add_argument(
        "--lengths", default=None, help="comma-separated subset of lengths"
    )
    parser.add_argument(
        "--items", type=int, default=None, help="only the first N items"
    )
    parser.add_argument("--run-id", default=None, help="name the run")
    parser.add_argument("--resume", metavar="ID", default=None)
    parser.add_argument(
        "--pilot", action="store_true", help="stop after the sizing gate"
    )
    parser.add_argument(
        "--smoke", action="store_true", help="flash, 2K and 4K, 3 items"
    )
    parser.add_argument("--rescore", metavar="ID", default=None)
    parser.add_argument("--reproduce", metavar="ID", default=None)
    parser.add_argument("--snapshot", metavar="ID", default=None)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--run-dir", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--model", default=None, help=argparse.SUPPRESS)
    return parser


def _run_dir(run_id: str) -> Path:
    for base in (RESULTS_DIR, RUNS_DIR):
        if (base / run_id / summarize.MANIFEST).exists():
            return base / run_id
    raise FileNotFoundError(
        f"no probe run {run_id!r} in results/context or evals/context/runs"
    )


def _write_manifest(run_dir: Path, manifest: ProbeManifest) -> None:
    text = manifest.model_dump_json(indent=2) + "\n"
    write_atomic(run_dir / summarize.MANIFEST, text)


def _verdict_lines(run_dir: Path) -> list[str]:
    lines = []
    for verdict in summarize.summarize(run_dir).verdicts:
        cap = f"cap {verdict.cap}" if verdict.cap else "no cap"
        if verdict.first_failure_length is None:
            detail = "no failure"
        else:
            reason = verdict.first_failure_reason
            where = (
                f" at {verdict.first_failure_depth}"
                if verdict.first_failure_depth
                else ""
            )
            detail = f"first failure at {verdict.first_failure_length}: {reason}{where}"
        lines.append(f"{verdict.model}: {cap} ({detail})")
    return lines


def _rescore(run_id: str) -> int:
    run_dir = _run_dir(run_id)
    print(f"summary: {summarize.write_summary(run_dir)}")
    print("\n".join(_verdict_lines(run_dir)))
    return 0


def _snapshot(run_id: str) -> int:
    source = RESULTS_DIR / run_id
    manifest = summarize.load_manifest(source)
    finished = (source / summarize.SUMMARY).exists()
    if not (finished and manifest.canonical and manifest.sizing_passed):
        raise ValueError(
            f"{run_id} is not a finished canonical run whose sizing gate passed; "
            "only those are snapshotted into evals/context/runs"
        )
    target = RUNS_DIR / run_id
    for path in sorted(source.iterdir()):
        if path.name in (summarize.MANIFEST, summarize.SUMMARY) or path.name.startswith(
            "rows-"
        ):
            copy_atomic(path, target / path.name)
    dataset = Path(manifest.dataset_path)
    copy_atomic(
        dataset if dataset.is_absolute() else REPO_ROOT / dataset,
        target / summarize.DATASET_COPY,
    )
    print(f"snapshot: {target}")
    return 0


def _model_names(args: argparse.Namespace) -> list[str]:
    if args.smoke:
        return ["flash"]
    names = args.models.split(",") if args.models else list(models.REGISTRY)
    for name in names:
        models.get(name)
    return names


def _lengths(args: argparse.Namespace) -> list[int]:
    if args.smoke:
        return list(SMOKE_LENGTHS)
    if not args.lengths:
        return list(LENGTHS)
    chosen = {int(value) for value in args.lengths.split(",")} | {BASELINE_LENGTH}
    unknown = chosen - set(LENGTHS)
    if unknown:
        raise ValueError(
            f"unknown lengths {sorted(unknown)}; choose from {list(LENGTHS)}"
        )
    return sorted(chosen)


def _new_manifest(args: argparse.Namespace) -> ProbeManifest:
    # import-placement:allow - transformers loads only when a run starts
    from transformers import AutoProcessor

    names = _model_names(args)
    model_dir = models.resolve_dir(names[0], override=False)
    if model_dir is None:
        raise FileNotFoundError(
            f"model {names[0]} is not pulled; run: ember model pull {names[0]}"
        )
    processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True)  # nosec B615
    js = runtime.joint_module(model_dir)

    def count(item: dict[str, object]) -> int:
        request = {
            "model": "clef-flash",
            "state": item["state"],
            "questions": item["questions"],
        }
        return request_size.measure(js, processor, request).total

    kept, excluded = probe_items.select_items(probe_items.load_items(), count)
    limit = SMOKE_ITEMS if args.smoke else args.items
    if limit is not None:
        kept = kept[:limit]
    return probe_items.build_manifest(
        run_id=args.run_id or new_run_id(),
        canonical=not (args.smoke or args.items or args.lengths),
        model_names=names,
        kept=kept,
        excluded=excluded,
        lengths=_lengths(args),
        recommended_max_memory=int(torch.mps.recommended_max_memory()),
    )


def _reproduction(
    original: ProbeManifest, run_dir: Path, items: int | None
) -> ProbeManifest:
    item_ids = original.item_ids[:items] if items else original.item_ids
    size = min(EXPLORATORY_ITEMS, len(item_ids))
    if item_ids == original.item_ids:
        exploratory = original.exploratory_item_ids
    else:
        pool = summarize.dataset_items(original, run_dir)
        exploratory = probe_items.exploratory_subset(
            [pool[i] for i in item_ids], size, SEED
        )
    return original.model_copy(
        update={
            "run_id": new_run_id(),
            "canonical": False,
            "item_ids": item_ids,
            "exploratory_items": size,
            "exploratory_item_ids": exploratory,
            **probe_items.provenance_fields(),
        }
    )


def _run_worker(run_dir: Path, model: str, *, pilot: bool = False) -> int:
    argv = [
        sys.executable,
        __file__,
        "--worker",
        "--run-dir",
        str(run_dir),
        "--model",
        model,
    ]
    command = [*argv, *(["--pilot"] if pilot else [])]
    return subprocess.run(command, check=False).returncode  # noqa: S603 - own script


def _gate_result(manifest: ProbeManifest, width: float) -> ProbeManifest:
    """Record the pilot's half-width; a failed gate is never canonical."""
    passed = width <= manifest.tolerance_accuracy
    return manifest.model_copy(
        update={
            "pilot_projected_half_width": round(width, 6)
            if math.isfinite(width)
            else None,
            "sizing_passed": passed,
            "canonical": manifest.canonical and passed,
        }
    )


def _sizing_gate(run_dir: Path, manifest: ProbeManifest) -> ProbeManifest | None:
    """Run the pilot and record its half-width; ``None`` if the worker failed."""
    model = "flash" if "flash" in manifest.models else next(iter(manifest.models))
    if _run_worker(run_dir, model, pilot=True) != 0:
        return None
    items = summarize.dataset_items(manifest, run_dir)
    rows = [
        row
        for row in read_rows(run_dir / summarize.rows_name(model))
        if row.depth is Depth.MIDDLE and row.status is RowStatus.OK
    ]

    def accuracy(length: int) -> dict[str, float]:
        return {
            row.item_id: item_scores(items[row.item_id], row.answers).accuracy
            for row in rows
            if row.length == length
        }

    width = projected_half_width(
        paired_deltas(accuracy(BASELINE_LENGTH), accuracy(_GATE_LENGTH))
    )
    updated = _gate_result(manifest, width)
    _write_manifest(run_dir, updated)
    print(
        f"sizing gate: projected half-width {width:.4f} "
        f"over {len(manifest.item_ids)} items",
        file=sys.stderr,
    )
    return updated


def _prepare(args: argparse.Namespace) -> tuple[Path, ProbeManifest, Path | None]:
    if args.resume:
        run_dir = RESULTS_DIR / args.resume
        return run_dir, summarize.load_manifest(run_dir), None
    if args.reproduce:
        original_dir = _run_dir(args.reproduce)
        manifest = _reproduction(
            summarize.load_manifest(original_dir), original_dir, args.items
        )
    else:
        original_dir, manifest = None, _new_manifest(args)
    run_dir = RESULTS_DIR / manifest.run_id
    if (run_dir / summarize.MANIFEST).exists():
        raise FileExistsError(
            f"{run_dir} already exists; use --resume {manifest.run_id}"
        )
    run_dir.mkdir(parents=True)
    _write_manifest(run_dir, manifest)
    if original_dir is not None and (original_dir / summarize.DATASET_COPY).exists():
        # A snapshot carries its own dataset; the reproduction must score that copy.
        dataset = summarize.DATASET_COPY
        copy_atomic(original_dir / dataset, run_dir / dataset)
    return run_dir, manifest, original_dir


def main(argv: list[str] | None = None) -> int:
    """Run the probe: 0 done, 1 on an error, 2 on a gate or reproduction failure."""
    args = _parser().parse_args(argv)
    try:
        if args.rescore:
            return _rescore(args.rescore)
        if args.snapshot:
            return _snapshot(args.snapshot)
        if not torch.backends.mps.is_available():
            print(
                "error: the long-context probe measures MPS memory and quality, and no "
                "MPS device is available here; run it on an Apple Silicon Mac.",
                file=sys.stderr,
            )
            return 1
        if args.worker:
            return worker.run_model(Path(args.run_dir), args.model, pilot=args.pilot)
        if process.is_up(str(config.resolve("host")), int(config.resolve("port"))):
            print(
                "warning: an ember server is running and shares unified memory with "
                "the probe; `ember stop` it for clean memory numbers.",
                file=sys.stderr,
            )
        run_dir, manifest, original_dir = _prepare(args)
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"run: {run_dir}", file=sys.stderr)
    if manifest.sizing_passed is False:
        print(
            "error: this run's sizing gate failed (projected half-width "
            f"{manifest.pilot_projected_half_width}); decide with a human before "
            "spending the full run",
            file=sys.stderr,
        )
        return 2
    if manifest.sizing_passed is None and _GATE_LENGTH in manifest.lengths:
        gated = _sizing_gate(run_dir, manifest)
        if gated is None:
            return 1
        if not gated.sizing_passed or args.pilot:
            return 0 if gated.sizing_passed else 2
    for model in manifest.models:
        if _run_worker(run_dir, model) != 0:
            return 1
    print(f"summary: {summarize.write_summary(run_dir)}", file=sys.stderr)
    print("\n".join(_verdict_lines(run_dir)))
    if original_dir is not None:
        differences = reproduce.compare(
            original_dir, run_dir, rows_only=bool(args.items)
        )
        for line in differences:
            print(f"differs: {line}")
        return 2 if differences else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
