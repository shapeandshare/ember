"""Match a snapshotted long-context probe to a leaderboard row."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .records.depth import Depth
from .records.probe_shape import ProbeShape

SNAPSHOTS_DIR = Path(__file__).parent / "runs"


def probe_shape(
    row: Mapping[str, Any],
    snapshots_dir: Path = SNAPSHOTS_DIR,
) -> ProbeShape | None:
    """Return the row's long-context shape from the newest matching snapshot.

    A snapshot matches when its manifest's ``device`` and ``dtype`` equal the
    row's, its ``dataset_content_sha256`` equals the row's dataset version, and
    the row's model repo is one of the manifest's models. ``None`` means
    "not measured".

    Parameters
    ----------
    row : Mapping[str, Any]
        A leaderboard row (``device``, ``dtype``, ``dataset_content_sha256``,
        ``model_repo``).
    snapshots_dir : Path
        Where canonical probe snapshots live (``evals/context/runs/``).

    Returns
    -------
    ProbeShape | None
        The three figures, or ``None`` when no snapshot matches.
    """
    if not snapshots_dir.is_dir():
        return None
    matched: ProbeShape | None = None
    for run_dir in sorted(snapshots_dir.glob("*/")):
        manifest_path = run_dir / "manifest.json"
        summary_path = run_dir / "summary.json"
        if not (manifest_path.is_file() and summary_path.is_file()):
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("device") != row.get("device"):
            continue
        if manifest.get("dtype") != row.get("dtype"):
            continue
        if manifest.get("dataset_content_sha256") != row.get(
            "dataset_content_sha256"
        ):
            continue
        names = [
            name
            for name, model in (manifest.get("models") or {}).items()
            if model.get("repo") == row.get("model_repo")
        ]
        if not names:
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        verdict = next(
            (
                entry
                for entry in summary.get("verdicts", [])
                if entry.get("model") == names[0]
            ),
            None,
        )
        if verdict is None:
            continue
        depth = verdict.get("first_failure_depth")
        matched = ProbeShape(
            request_cap=verdict.get("cap"),
            first_drop_length=verdict.get("first_failure_length"),
            worst_depth=Depth(depth) if depth else None,
        )
    return matched
