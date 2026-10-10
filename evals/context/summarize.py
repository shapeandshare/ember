"""Build the probe summary from a run's rows and manifest, byte for byte."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..eval.provenance import REPO_ROOT
from ..export import write_atomic
from .records.cell_result import CellResult
from .records.depth import Depth
from .records.probe_manifest import ProbeManifest
from .records.probe_row import ProbeRow
from .records.probe_summary import ProbeSummary
from .records.row_status import RowStatus
from .rows_file import read_rows
from .rule import LengthMemory, evaluate
from .scoring import ItemScore, cell_ece, delta_ci, item_scores, paired_deltas

DECIMALS = 6
MANIFEST = "manifest.json"
SUMMARY = "summary.json"
DATASET_COPY = "dataset.jsonl"
_DEPTH_ORDER = {depth: index for index, depth in enumerate(Depth)}


def rows_name(model: str) -> str:
    """Return the rows file name for ``model``."""
    return f"rows-{model}.jsonl"


def load_manifest(run_dir: Path) -> ProbeManifest:
    """Read ``run_dir/manifest.json``."""
    text = (run_dir / MANIFEST).read_text(encoding="utf-8")
    return ProbeManifest.model_validate_json(text)


def dataset_items(
    manifest: ProbeManifest, run_dir: Path | None = None
) -> dict[str, dict[str, Any]]:
    """Return the manifest's dataset by item id, after checking its SHA-256.

    A copy in ``run_dir`` (a snapshot) wins over the path the manifest records.

    Raises
    ------
    ValueError
        If the dataset's digest differs from the manifest's.
    """
    path = Path(manifest.dataset_path)
    if run_dir is not None and (run_dir / DATASET_COPY).exists():
        path = run_dir / DATASET_COPY
    elif not path.is_absolute():
        path = REPO_ROOT / path
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != manifest.dataset_sha256:
        raise ValueError(
            f"the dataset at {path.name} has SHA-256 {digest}, but the manifest "
            f"pinned {manifest.dataset_sha256}"
        )
    lines = data.decode("utf-8").splitlines()
    return {item["id"]: item for item in (json.loads(x) for x in lines if x.strip())}


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, DECIMALS)
    if isinstance(value, dict):
        return {key: _rounded(inner) for key, inner in value.items()}
    if isinstance(value, list | tuple):
        return [_rounded(inner) for inner in value]
    return value


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _order(row: ProbeRow) -> tuple[str, int, int, str]:
    return (row.model, row.length, _DEPTH_ORDER[row.depth], row.item_id)


def _cells(
    model: str,
    rows: list[ProbeRow],
    items: dict[str, dict[str, Any]],
    manifest: ProbeManifest,
) -> list[CellResult]:
    scores: dict[tuple[int, Depth], dict[str, ItemScore]] = defaultdict(dict)
    exploratory: dict[tuple[int, Depth], bool] = {}
    for row in rows:
        if row.status is not RowStatus.OK:
            continue
        cell = (row.length, row.depth)
        scores[cell][row.item_id] = item_scores(items[row.item_id], row.answers)
        exploratory[cell] = exploratory.get(cell, True) and row.exploratory
    baseline_length = manifest.lengths[0]
    cells: list[CellResult] = []
    ordered = sorted(scores, key=lambda cell: (cell[0], _DEPTH_ORDER[cell[1]]))
    for length, depth in ordered:
        by_item = scores[(length, depth)]
        base = scores.get((baseline_length, depth), {})
        accuracy = paired_deltas(
            {k: s.accuracy for k, s in base.items()},
            {k: s.accuracy for k, s in by_item.items()},
        )
        brier = paired_deltas(
            {k: s.brier for k, s in base.items()},
            {k: s.brier for k, s in by_item.items()},
        )
        baseline = length == baseline_length
        ci = {
            "resamples": manifest.bootstrap_resamples,
            "level": manifest.bootstrap_level,
            "seed": manifest.seed,
        }
        pooled = list(by_item.values())
        cells.append(
            CellResult(
                **_rounded(
                    {
                        "model": model,
                        "length": length,
                        "depth": depth,
                        "exploratory": exploratory[(length, depth)],
                        "n_items": len(by_item),
                        "accuracy": _mean([s.accuracy for s in pooled]),
                        "brier": _mean([s.brier for s in pooled]),
                        "ece": cell_ece(
                            [c for s in pooled for c in s.confidences],
                            [ok for s in pooled for ok in s.correct],
                        ),
                        "delta_accuracy": 0.0 if baseline else _mean(accuracy),
                        "delta_accuracy_ci": (0.0, 0.0)
                        if baseline
                        else delta_ci(accuracy, **ci),
                        "delta_brier": 0.0 if baseline else _mean(brier),
                        "delta_brier_ci": (0.0, 0.0)
                        if baseline
                        else delta_ci(brier, **ci),
                    }
                )
            )
        )
    return cells


def _memory(rows: list[ProbeRow]) -> dict[int, LengthMemory]:
    grouped: dict[int, list[ProbeRow]] = defaultdict(list)
    for row in rows:
        grouped[row.length].append(row)
    memory: dict[int, LengthMemory] = {}
    for length, group in grouped.items():
        latencies = [r.latency_ms for r in group if r.status is RowStatus.OK]
        memory[length] = LengthMemory(
            peak_bytes=max(r.peak_bytes for r in group),
            oom=any(r.status is RowStatus.OOM for r in group),
            latency_ms_median=round(statistics.median(latencies), DECIMALS)
            if latencies
            else None,
        )
    return memory


def _rule(manifest: ProbeManifest) -> dict[str, Any]:
    return {
        "tolerance_accuracy": manifest.tolerance_accuracy,
        "tolerance_brier": manifest.tolerance_brier,
        "memory_budget_bytes": {
            name: spec.memory_budget_bytes for name, spec in manifest.models.items()
        },
        "lengths": manifest.lengths,
        "depths": [depth.value for depth in manifest.depths],
        "length_tolerance_tokens": manifest.length_tolerance_tokens,
    }


def summarize(run_dir: Path) -> ProbeSummary:
    """Rebuild the summary from ``run_dir``'s manifest and rows.

    Raises
    ------
    ValueError
        If the dataset changed since the manifest, or a row key repeats.
    """
    manifest = load_manifest(run_dir)
    items = dataset_items(manifest, run_dir)
    inputs = {MANIFEST: _sha256(run_dir / MANIFEST)}
    cells: list[CellResult] = []
    lengths = []
    verdicts = []
    for model in sorted(manifest.models):
        path = run_dir / rows_name(model)
        if path.exists():
            inputs[path.name] = _sha256(path)
        rows = sorted(read_rows(path), key=_order)
        keys = [row.key for row in rows]
        if len(set(keys)) != len(keys):
            raise ValueError(f"{path.name} has a duplicate row key")
        model_cells = _cells(model, rows, items, manifest)
        model_lengths, verdict = evaluate(
            model_cells,
            _memory(rows),
            model=model,
            tolerance_accuracy=manifest.tolerance_accuracy,
            tolerance_brier=manifest.tolerance_brier,
            budget_bytes=manifest.models[model].memory_budget_bytes,
            depths=manifest.depths,
        )
        cells += model_cells
        lengths += model_lengths
        verdicts.append(verdict)
    return ProbeSummary(
        run_id=manifest.run_id,
        canonical=manifest.canonical,
        rule=_rule(manifest),
        cells=cells,
        lengths=lengths,
        verdicts=verdicts,
        inputs_sha256=inputs,
    )


def render(summary: ProbeSummary) -> str:
    """Serialize a summary: sorted keys, two-space indent, 6-decimal floats."""
    body = _rounded(summary.model_dump(mode="json"))
    return json.dumps(body, sort_keys=True, indent=2) + "\n"


def write_summary(run_dir: Path) -> Path:
    """Write ``run_dir/summary.json`` atomically and return its path."""
    path = run_dir / SUMMARY
    write_atomic(path, render(summarize(run_dir)))
    return path
