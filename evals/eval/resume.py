"""Run manifests and resumption for the benchmark harness (specs/004 FR-066).

A manifest is written before the first request so an interrupted run can be
continued under its own id, provided the server and the dataset's scored
content are unchanged. Trace rows are appended through the probe's torn-line
safe writer and re-read to find the items already scored.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..atomic import write_atomic

SETTINGS_KEYS = ("dtype", "max_length", "max_request_length")


class RunManifest(BaseModel):
    """What a run was started against; compared on resume.

    Parameters
    ----------
    run_id, model, deployment_label : str
        The run's identity.
    settings : dict[str, Any]
        The engine's ``dtype``, ``max_length``, ``max_request_length``.
    dataset_sha256, dataset_content_sha256 : str
        The dataset file's bytes hash and its content hash (the version).
    recipe_sha256 : dict[str, str]
        Per-recipe content hashes.
    register_sha256 : str | None
        The data-source register's hash.
    split, category : str | None
        The run's filters.
    started_at : str
        UTC timestamp.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str
    model: str
    deployment_label: str
    settings: dict[str, Any]
    dataset_sha256: str
    dataset_content_sha256: str
    recipe_sha256: dict[str, str]
    register_sha256: str | None
    split: str | None
    category: str | None
    started_at: str


def settings_from(engine: Mapping[str, Any]) -> dict[str, Any]:
    """Return the comparable engine settings from a ``/health`` engine block."""
    return {key: engine.get(key) for key in SETTINGS_KEYS}


def manifest_path(results_dir: Path, run_id: str) -> Path:
    """Return where ``run_id``'s manifest lives."""
    return results_dir / f"{run_id}_run.json"


def write(path: Path, manifest: RunManifest) -> None:
    """Write the manifest atomically."""
    write_atomic(path, manifest.model_dump_json(indent=2) + "\n")


def read(path: Path) -> RunManifest:
    """Read a manifest."""
    return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))


def mismatches(
    manifest: RunManifest,
    *,
    model: str,
    engine: Mapping[str, Any],
    dataset_content_sha256: str,
    split: str | None,
    category: str | None,
) -> list[str]:
    """Return the fields that differ between the manifest and the live run.

    The content hash is compared, not the file hash, so annotation-only edits
    (kind, tier, source, rationale) never block a resume.
    """
    problems: list[str] = []
    if manifest.model != model:
        problems.append(f"model: manifest {manifest.model!r}, live {model!r}")
    live = settings_from(engine)
    for key in SETTINGS_KEYS:
        if manifest.settings.get(key) != live.get(key):
            recorded, current = manifest.settings.get(key), live.get(key)
            problems.append(f"{key}: manifest {recorded!r}, live {current!r}")
    if manifest.dataset_content_sha256 != dataset_content_sha256:
        problems.append(
            f"dataset_content_sha256: manifest {manifest.dataset_content_sha256[:12]}, "
            f"current {dataset_content_sha256[:12]} "
            "(a gold, state, question, or split changed)"
        )
    if manifest.split != split:
        problems.append(f"split: manifest {manifest.split!r}, requested {split!r}")
    if manifest.category != category:
        problems.append(
            f"category: manifest {manifest.category!r}, requested {category!r}"
        )
    return problems


def done_ids(trace_path: Path) -> set[str]:
    """Return the ids already in a trace, ignoring a torn final line."""
    if not trace_path.exists():
        return set()
    ids: set[str] = set()
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ids.add(str(json.loads(line)["id"]))
        except (ValueError, KeyError):
            continue
    return ids


def read_rows(trace_path: Path) -> list[dict[str, Any]]:
    """Return the complete rows of a trace, dropping a torn final line."""
    rows: list[dict[str, Any]] = []
    if not trace_path.exists():
        return rows
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def repair(trace_path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """Rewrite the trace with only its complete rows (drops a torn tail)."""
    write_atomic(trace_path, "".join(json.dumps(row) + "\n" for row in rows))
