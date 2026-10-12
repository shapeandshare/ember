"""Unit tests for linking a probe snapshot to a leaderboard row (US5)."""

from __future__ import annotations

import json
from pathlib import Path

from evals.context.link import probe_shape
from evals.context.records.probe_shape import ProbeShape

ROW = {
    "device": "mps",
    "dtype": "float16",
    "dataset_content_sha256": "v1",
    "model_repo": "Cloudflare/clef-flash",
}


def _snapshot(
    root: Path,
    run_id: str,
    *,
    device: str = "mps",
    dtype: str = "float16",
    version: str = "v1",
    repo: str = "Cloudflare/clef-flash",
    cap: int | None = 24576,
    drop: int | None = 32768,
    depth: str | None = "end",
) -> None:
    run = root / run_id
    run.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "device": device,
        "dtype": dtype,
        "dataset_content_sha256": version,
        "models": {
            "flash": {"name": "flash", "repo": repo, "revision": "r", "params": "9B"}
        },
    }
    summary = {
        "run_id": run_id,
        "verdicts": [
            {
                "model": "flash",
                "cap": cap,
                "first_failure_length": drop,
                "first_failure_reason": "accuracy" if drop else None,
                "first_failure_depth": depth if drop else None,
            }
        ],
    }
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


def test_a_matching_snapshot_returns_the_shape(tmp_path: Path) -> None:
    _snapshot(tmp_path, "context_20261011T000000Z")
    shape = probe_shape(ROW, tmp_path)
    assert isinstance(shape, ProbeShape)
    assert shape.request_cap == 24576
    assert shape.first_drop_length == 32768
    assert shape.worst_depth is not None
    assert shape.worst_depth.value == "end"


def test_every_key_must_match(tmp_path: Path) -> None:
    _snapshot(tmp_path, "context_a_20261011T000000Z", device="cuda")
    _snapshot(tmp_path, "context_b_20261011T000000Z", dtype="bfloat16")
    _snapshot(tmp_path, "context_c_20261011T000000Z", version="v2")
    _snapshot(tmp_path, "context_d_20261011T000000Z", repo="other/model")
    assert probe_shape(ROW, tmp_path) is None


def test_the_newest_matching_snapshot_wins(tmp_path: Path) -> None:
    _snapshot(tmp_path, "context_20261010T000000Z", cap=2048)
    _snapshot(tmp_path, "context_20261011T000000Z", cap=24576)
    shape = probe_shape(ROW, tmp_path)
    assert shape is not None
    assert shape.request_cap == 24576


def test_missing_or_empty_snapshots_return_none(tmp_path: Path) -> None:
    assert probe_shape(ROW, tmp_path) is None
    assert probe_shape(ROW, tmp_path / "nope") is None


def test_the_leaderboard_row_carries_the_probe_or_none() -> None:
    """A row without a matching snapshot says ``probe: None``."""
    import json as _json
    from pathlib import Path as _Path

    from evals.leaderboard import build

    bundle = _Path(__file__).resolve().parents[1] / "benchmark" / "flash_20261012T014702Z"
    model = _json.loads((bundle / "model.json").read_text(encoding="utf-8"))
    board = build([model])
    for version in board["versions"]:
        for row in version["rows"]:
            assert "probe" in row
            assert row["probe"] is None, "no snapshot exists yet"
