"""The landing page's benchmark numbers come from the published benchmark run."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_site_benchmark.py"


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


def test_build_writes_the_headline_into_the_site_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "_data").mkdir()
    monkeypatch.setattr(bench, "SITE", tmp_path)
    monkeypatch.setattr(bench, "OUT", tmp_path / "results")
    assert bench.build() == 0
    written = tmp_path / "_data" / "benchmark.json"
    data = json.loads(written.read_text(encoding="utf-8"))
    model = json.loads(bench._latest_model().read_text(encoding="utf-8"))
    assert data["headline"] == bench.headline(model)
