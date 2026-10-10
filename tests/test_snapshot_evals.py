"""The tracked benchmark snapshot's results.json must not carry a raw
server URL or model storage location — only model.json was previously
scrubbed (``evals.analysis.build``); ``snapshot_evals.py`` used to copy
the raw ``results.json`` byte-for-byte into the committed bundle,
re-leaking the same real URL/S3 path it had just stripped from
``model.json`` (vault/decisions/2026-10-10-generic-deployment-labels.md).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from evals.eval import snapshot_evals
from evals.metrics import aggregate, score_item

from tests.test_eval_benchmark import DATASET, ITEMS, _answers


@pytest.fixture
def real_results(tmp_path: Path) -> Path:
    """A results.json shaped like a real hosted run, with real-looking
    sensitive values (a server URL, an S3 model location)."""
    run_id = "clef-flash_20261010T000000Z"
    result = metrics_result = score_item(ITEMS[0], _answers(ITEMS[0], right=True))
    metrics_result.update(latency_ms=900.0, model="clef-flash", usage={}, answers={})
    trace = tmp_path / f"{run_id}_trace.jsonl"
    trace.write_text(json.dumps(result) + "\n", encoding="utf-8")
    config = {
        "run_id": run_id,
        "timestamp": "20261010T000000Z",
        "git_hash": "abc1234",
        "model": "clef-flash",
        "model_spec": {},
        "engine": {
            "model": "s3://real-bucket-name/real-prefix/clef-flash/artifacts/model_file",
            "device": "cuda",
            "dtype": "float16",
        },
        "deployment_label": "Remote hosted (GPU, CUDA)",
        "host": {
            "platform": "macOS-26.0-arm64",
            "cpu": "Apple M4 Max",
            "python": "3.12.11",
            "packages": {"ember-advise": "0.10.3"},
        },
        "server": "https://api-c-realhostid123.merced.obp.outerbounds.com",
        "dataset": DATASET.name,
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "trace": trace.name,
        "split": None,
        "category": None,
        "n_items": 1,
        "n_errors": 0,
        "latency_ms": {"mean": 900.0, "p50": 900.0, "p95": 900.0, "max": 900.0},
    }
    results = tmp_path / f"{run_id}_results.json"
    results.write_text(
        json.dumps({"config": config, "summary": aggregate([result])}),
        encoding="utf-8",
    )
    return results


def test_snapshot_scrubs_the_server_url_from_the_committed_results_json(
    real_results: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The committed bundle's ``results.json`` — not just ``model.json`` —
    must not carry the raw server URL.
    """
    benchmark_dir = tmp_path / "benchmark"
    monkeypatch.setattr(snapshot_evals, "BENCHMARK_DIR", benchmark_dir)
    out = snapshot_evals.snapshot(real_results)
    committed = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert "server" not in committed["config"]
    serialized = json.dumps(committed)
    assert "outerbounds.com" not in serialized
    assert "realhostid123" not in serialized


def test_snapshot_scrubs_the_model_storage_location_from_committed_results_json(
    real_results: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The committed bundle's ``results.json`` must not carry a real S3 URI
    or local filesystem path in ``config.engine``.
    """
    benchmark_dir = tmp_path / "benchmark"
    monkeypatch.setattr(snapshot_evals, "BENCHMARK_DIR", benchmark_dir)
    out = snapshot_evals.snapshot(real_results)
    committed = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert "model" not in committed["config"]["engine"]
    assert committed["config"]["engine"]["device"] == "cuda"
    serialized = json.dumps(committed)
    assert "real-bucket-name" not in serialized


def test_snapshot_keeps_the_deployment_label_in_committed_results_json(
    real_results: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The generic ``deployment_label`` must survive into the committed
    bundle — only the raw, sensitive fields are stripped.
    """
    benchmark_dir = tmp_path / "benchmark"
    monkeypatch.setattr(snapshot_evals, "BENCHMARK_DIR", benchmark_dir)
    out = snapshot_evals.snapshot(real_results)
    committed = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert committed["config"]["deployment_label"] == "Remote hosted (GPU, CUDA)"
