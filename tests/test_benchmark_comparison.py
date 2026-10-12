"""The Phase 1 controlled-comparison gate (specs/006-benchmark-hygiene, US2).

Two committed bundles — MPS and CUDA, float16, the same dataset content hash,
with identical settings — render side by side. These tests are the phase gate:
they fail until the MPS half is committed alongside the CUDA one.
"""

from __future__ import annotations

import json
from pathlib import Path

from evals.dataset import hashes, io
from evals.eval.report_compare import render_compare

BENCHMARK = Path(__file__).resolve().parents[1] / "benchmark"


def _metas() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))["meta"]
        for path in BENCHMARK.glob("*/model.json")
    ]


def _newest(device: str, version: str) -> dict | None:
    candidates = [
        meta
        for meta in _metas()
        if (meta.get("engine") or {}).get("device") == device
        and meta.get("dataset_content_sha256") == version
    ]
    return max(candidates, key=lambda meta: meta["run_at"], default=None)


def _pair() -> tuple[dict, dict]:
    current = hashes.dataset_content_sha256(io.read_items(io.DATASET_PATH))
    mps = _newest("mps", current)
    cuda = _newest("cuda", current)
    assert mps is not None, "no MPS bundle on the current dataset version"
    assert cuda is not None, "no CUDA bundle on the current dataset version"
    return mps, cuda


def test_both_halves_are_float16_with_hashes() -> None:
    """Both runs are float16 and carry their per-recipe hashes."""
    mps, cuda = _pair()
    for meta in (mps, cuda):
        assert meta["settings"]["dtype"] == "float16"
        assert meta["recipe_sha256"], "each bundle must carry per-recipe hashes"


def test_the_pair_differs_only_in_the_device() -> None:
    """Settings and dataset version are identical; only the device differs."""
    mps, cuda = _pair()
    assert mps["settings"] == cuda["settings"]
    assert mps["dataset_content_sha256"] == cuda["dataset_content_sha256"]
    assert mps["engine"]["device"] == "mps"
    assert cuda["engine"]["device"] == "cuda"


def test_the_comparison_view_renders_the_pair() -> None:
    """The pair renders side by side through the existing comparison view."""
    mps, cuda = _pair()
    a = json.loads(
        (BENCHMARK / mps["run_id"] / "results.json").read_text(encoding="utf-8")
    )
    b = json.loads(
        (BENCHMARK / cuda["run_id"] / "results.json").read_text(encoding="utf-8")
    )
    text = render_compare(a, b)
    assert "comparison" in text
    assert mps["run_id"] in text
    assert cuda["run_id"] in text


def test_the_leaderboard_shows_both_rows_on_the_current_version() -> None:
    """The pair takes two distinct leaderboard rows (label|device keys differ)."""
    from evals.leaderboard import build

    current = hashes.dataset_content_sha256(io.read_items(io.DATASET_PATH))
    models = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(BENCHMARK.glob("*/model.json"))
    ]
    board = build(models)
    version = next(
        entry
        for entry in board["versions"]
        if entry.get("dataset_content_sha256") == current
    )
    keys = {(row["deployment_label"], row["device"]) for row in version["rows"]}
    mps, cuda = _pair()
    assert (mps["deployment_label"], "mps") in keys
    assert (cuda["deployment_label"], "cuda") in keys
