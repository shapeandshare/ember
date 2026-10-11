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


# ###########################################################################
# specs/004 Phase 0: snapshot --rebuild
# ###########################################################################


def _legacy_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """A pre-Phase-0 bundle: string sources in dataset.jsonl, no tokens, no hashes."""
    run_id = "clef-flash_20261001T000000Z"
    bundle = tmp_path / "benchmark" / run_id
    bundle.mkdir(parents=True)
    items = [dict(item) for item in ITEMS[:6] + [i for i in ITEMS if "images" in i][:2]]
    legacy = []
    for item in items:
        raw = dict(item)
        raw["source"] = "skill_md" if raw["id"] == "intent_001" else "curated"
        legacy.append(raw)
    (bundle / "dataset.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in legacy), encoding="utf-8"
    )
    scored = []
    for index, item in enumerate(items):
        result = score_item(item, _answers(item, right=index % 2 == 0))
        result.update(latency_ms=900.0, model="clef-flash", usage={}, answers={})
        scored.append(result)
    (bundle / "trace.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in scored), encoding="utf-8"
    )
    old_summary = aggregate(scored)
    config = {
        "run_id": run_id,
        "timestamp": "20261001T000000Z",
        "git_hash": "abc1234",
        "model": "clef-flash",
        "model_spec": {"name": "flash"},
        "engine": {"device": "mps", "dtype": "float16", "max_length": 262144},
        "deployment_label": "Local (Apple Silicon, MPS)",
        "host": {"platform": "macOS", "cpu": "M4", "python": "3.12", "packages": {}},
        "dataset": "clef-flash.jsonl",
        "dataset_file": "dataset.jsonl",
        "dataset_sha256": hashlib.sha256(
            (bundle / "dataset.jsonl").read_bytes()
        ).hexdigest(),
        "trace": "trace.jsonl",
        "split": None,
        "category": None,
        "n_items": len(items),
        "n_errors": 0,
        "latency_ms": {"mean": 900.0, "p50": 900.0, "p95": 900.0, "max": 900.0},
    }
    (bundle / "results.json").write_text(
        json.dumps({"config": config, "summary": old_summary}, indent=2),
        encoding="utf-8",
    )
    (bundle / "model.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(snapshot_evals, "BENCHMARK_DIR", tmp_path / "benchmark")
    return bundle, run_id


def test_rebuild_recomputes_the_summary_and_adds_the_phase_0_meta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from evals.dataset import hashes, io

    bundle, run_id = _legacy_bundle(tmp_path, monkeypatch)
    before = json.loads((bundle / "results.json").read_text())["summary"]
    assert snapshot_evals.main(["--rebuild", run_id]) == 0
    after = json.loads((bundle / "results.json").read_text())
    assert after["summary"]["categories"] == before["categories"]
    assert after["summary"]["questions"] == before["questions"]
    assert after["summary"]["overall"]["items"] == 6
    assert set(after["summary"]["capability"]["categories"]) <= {"vision_noul"}
    config = after["config"]
    items = io.read_items(bundle / "dataset.jsonl", legacy_dataset_version="0" * 64)
    assert config["dataset_content_sha256"] == hashes.dataset_content_sha256(items)
    assert config["recipe_sha256"] == hashes.recipe_hashes(items)
    assert config["register_sha256"] is None
    assert "server" not in config
    model = json.loads((bundle / "model.json").read_text())
    meta = model["meta"]
    assert meta["dataset_content_sha256"] == config["dataset_content_sha256"]
    assert meta["recipe_sha256"] == config["recipe_sha256"]
    assert meta["register_sha256"] is None
    assert meta["settings"] == {
        "dtype": "float16",
        "max_length": 262144,
        "max_request_length": None,
    }
    assert meta["tokens_available"] is False
    rows = [
        json.loads(line) for line in (bundle / "trace.jsonl").read_text().splitlines()
    ]
    assert all(row["source_kind"] == "authored" for row in rows)
    assert all("kind" in row and "tier" in row for row in rows)


def test_rebuild_requires_the_bundle_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, run_id = _legacy_bundle(tmp_path, monkeypatch)
    (bundle / "trace.jsonl").unlink()
    assert snapshot_evals.main(["--rebuild", run_id]) == 1
