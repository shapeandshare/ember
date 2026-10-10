"""The site's benchmark pages: a leaderboard index plus one full detail
report per tracked (model, deployment) run, built from every snapshotted
``benchmark/<run-id>/model.json``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_site_benchmark.py"
REAL_BENCHMARK = ROOT / "benchmark"


def _load_build_site_benchmark() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_site_benchmark", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bench = _load_build_site_benchmark()

MODEL = {
    "meta": {"host": {"cpu": "Apple M4 Max"}},
    "summary": {
        "overall": {
            "items": 264,
            "questions": 456,
            "accuracy": 0.8443,
            "accuracy_ci": [0.8092, 0.8772],
        },
        "choice": {
            "n": 192,
            "acting": {"n": 123, "coverage": 0.6406, "accuracy": 1.0},
            "reliability": [
                {
                    "low": 0.3,
                    "high": 0.4,
                    "n": 4,
                    "confidence": 0.3808,
                    "accuracy": 0.5,
                },
                {
                    "low": 0.9,
                    "high": 1.0,
                    "n": 104,
                    "confidence": 0.949,
                    "accuracy": 1.0,
                },
            ],
        },
        "noul": {"n": 168, "acting": {"n": 111, "coverage": 0.6607, "accuracy": 1.0}},
        "score": {"n": 96, "accuracy": 0.5312, "within_one": 0.8542},
    },
    "latency": {"p50": 922.5, "p95": 1091.1},
}


def _real_bundles() -> list[Path]:
    """Copy of every tracked ``benchmark/<run-id>/`` directory for a sandboxed build."""
    return sorted(REAL_BENCHMARK.glob("*/model.json"))


def test_headline_reports_the_numbers_the_landing_page_shows() -> None:
    assert bench.headline(MODEL) == {
        "items": 264,
        "questions": 456,
        "accuracy_pct": 84,
        "accuracy_ci_pct": [81, 88],
        "confident": {"answered": 234, "asked": 360, "correct": 234, "share_pct": 65},
        "score": {"exact_pct": 53, "within_one_pct": 85},
        "reliability": [
            {"claimed_pct": 38, "actual_pct": 50, "n": 4},
            {"claimed_pct": 95, "actual_pct": 100, "n": 104},
        ],
        "conservative": True,
        "latency": {"p50_s": "0.92", "p95_s": "1.09"},
        "host": "Apple M4 Max",
    }


def test_headline_is_not_conservative_when_a_band_overclaims() -> None:
    bands = MODEL["summary"]["choice"]["reliability"]
    overclaiming = {**bands[0], "confidence": 0.62, "accuracy": 0.5}
    choice = {**MODEL["summary"]["choice"], "reliability": [overclaiming, bands[1]]}
    model = {**MODEL, "summary": {**MODEL["summary"], "choice": choice}}
    assert bench.headline(model)["conservative"] is False


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy every real tracked bundle into a sandbox benchmark/ tree."""
    import shutil

    bundles = REAL_BENCHMARK.glob("*")
    sandbox_benchmark = tmp_path / "benchmark"
    sandbox_benchmark.mkdir()
    for run_dir in bundles:
        if run_dir.is_dir():
            shutil.copytree(run_dir, sandbox_benchmark / run_dir.name)
    sandbox_site = tmp_path / "site"
    (sandbox_site / "_data").mkdir(parents=True)
    (sandbox_site / "assets").mkdir()
    monkeypatch.setattr(bench, "BENCHMARK", sandbox_benchmark)
    monkeypatch.setattr(bench, "SITE", sandbox_site)
    monkeypatch.setattr(bench, "OUT", sandbox_site / "results")
    return sandbox_site


def test_build_writes_one_detail_page_set_per_leaderboard_row(sandbox: Path) -> None:
    assert bench.build() == 0
    data = json.loads(
        (sandbox / "_data" / "benchmark.json").read_text(encoding="utf-8")
    )
    run_ids = {row["run_id"] for row in data["leaderboard"]["rows"]}
    assert len(run_ids) >= 1
    for run_id in run_ids:
        run_dir = sandbox / "results" / run_id
        assert run_dir.is_dir(), f"missing detail pages for {run_id}"
        assert (run_dir / "summary.md").exists()


def test_build_writes_a_leaderboard_index_page(sandbox: Path) -> None:
    assert bench.build() == 0
    index = sandbox / "results" / "index.md"
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "permalink: /results/" in text


def test_build_writes_the_headline_from_the_top_leaderboard_row(
    sandbox: Path,
) -> None:
    assert bench.build() == 0
    data = json.loads(
        (sandbox / "_data" / "benchmark.json").read_text(encoding="utf-8")
    )
    rows = data["leaderboard"]["rows"]
    assert rows, "expected at least one leaderboard row"
    top_run_id = rows[0]["run_id"]
    model = json.loads(
        (sandbox.parent / "benchmark" / top_run_id / "model.json").read_text(
            encoding="utf-8"
        )
    )
    assert data["headline"] == bench.headline(model)


def test_build_with_no_tracked_runs_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_benchmark = tmp_path / "benchmark"
    empty_benchmark.mkdir()
    sandbox_site = tmp_path / "site"
    (sandbox_site / "_data").mkdir(parents=True)
    monkeypatch.setattr(bench, "BENCHMARK", empty_benchmark)
    monkeypatch.setattr(bench, "SITE", sandbox_site)
    monkeypatch.setattr(bench, "OUT", sandbox_site / "results")
    assert bench.build() == 1
