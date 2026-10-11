"""Benchmark runner, specs/004 Phase 0: the token-split requirement, per-row
annotations, the run manifest and hashes, and ``--resume``.

Synthetic three-item datasets and a patched ``_advise`` stand in for a server;
nothing here opens a port.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

SPLIT_USAGE = {
    "input_tokens": 10,
    "output_tokens": 0,
    "state_tokens": 2,
    "fixed_tokens": 8,
    "media_tokens": 0,
}


def _dataset(tmp_path: Any, count: int = 3) -> Any:
    from evals.dataset import io
    from evals.dataset.records.item import Item

    items = []
    for index in range(count):
        items.append(
            Item.model_validate(
                {
                    "id": f"item_{index:03d}",
                    "split": "dev" if index % 2 else "test",
                    "category": "intent_readiness",
                    "state": f"state {index}",
                    "questions": {
                        "intent": {
                            "type": "choice",
                            "instructions": "?",
                            "criteria": {"a": "A", "b": "B"},
                        }
                    },
                    "gold_labels": {"intent": "a"},
                    "rationale": "r",
                    "source": {"kind": "authored", "dataset_version": "0" * 64},
                    "kind": "control" if index == 0 else None,
                    "tier": "easy" if index == 1 else None,
                }
            )
        )
    path = tmp_path / "dataset.jsonl"
    io.write_items(path, items)
    return path


def _answers_for(item: dict[str, Any], usage: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": "clef-flash",
        "answers": {
            "intent": {
                "type": "choice",
                "choice": "a",
                "confidence": 0.9,
                "probabilities": {"a": 0.9, "b": 0.1},
            }
        },
        "usage": usage,
    }


def _patch(
    monkeypatch: Any, tmp_path: Any, advise: Any, health: Any | None = None
) -> Any:
    from evals.eval import run_evals as module

    monkeypatch.setattr(module, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(
        module,
        "_health",
        health
        or (
            lambda server: {
                "engine": {
                    "device": "mps",
                    "dtype": "float16",
                    "max_length": 10,
                    "max_request_length": 5,
                },
                "version": "0.12.0",
            }
        ),
    )
    monkeypatch.setattr(module, "_advise", advise)
    return module


def test_run_refuses_a_server_without_the_token_split(
    monkeypatch: Any, tmp_path: Any, capsys: Any
) -> None:
    module = _patch(
        monkeypatch,
        tmp_path,
        lambda server, item: _answers_for(
            item, {"input_tokens": 10, "output_tokens": 0}
        ),
    )
    assert module.run_evals("http://127.0.0.1:1", dataset_path=_dataset(tmp_path)) == 1
    err = capsys.readouterr().err
    assert "does not return the token split" in err
    assert "0.12.0" in err
    assert not list((tmp_path / "results").glob("*_trace.jsonl")) or all(
        not p.read_text() for p in (tmp_path / "results").glob("*_trace.jsonl")
    )


def test_run_records_tokens_annotations_manifest_and_hashes(
    monkeypatch: Any, tmp_path: Any
) -> None:
    seen: list[bool] = []

    def advise(server: str, item: dict[str, Any]) -> dict[str, Any]:
        seen.append((tmp_path / "results").glob("*_run.json") is not None)
        manifests = list((tmp_path / "results").glob("*_run.json"))
        assert manifests, "the manifest must exist before the first request"
        return _answers_for(item, SPLIT_USAGE)

    module = _patch(monkeypatch, tmp_path, advise)
    dataset = _dataset(tmp_path)
    assert module.run_evals("http://127.0.0.1:1", dataset_path=dataset) == 0
    results_dir = tmp_path / "results"
    trace = [
        json.loads(line)
        for line in next(results_dir.glob("*_trace.jsonl")).read_text().splitlines()
    ]
    assert len(trace) == 3
    for row in trace:
        assert row["tokens"] == {"total": 10, "state": 2, "fixed": 8, "media": 0}
        assert {"kind", "tier", "source_kind", "parent_id", "perturbation"} <= set(row)
        assert row["source_kind"] == "authored"
    assert trace[0]["kind"] == "control"
    assert trace[1]["tier"] == "easy"
    manifest = json.loads(next(results_dir.glob("*_run.json")).read_text())
    for key in (
        "run_id",
        "model",
        "deployment_label",
        "settings",
        "dataset_sha256",
        "dataset_content_sha256",
        "recipe_sha256",
        "register_sha256",
        "split",
        "category",
        "started_at",
    ):
        assert key in manifest, key
    assert manifest["settings"] == {
        "dtype": "float16",
        "max_length": 10,
        "max_request_length": 5,
    }
    config = json.loads(next(results_dir.glob("*_results.json")).read_text())["config"]
    for key in (
        "dataset_content_sha256",
        "recipe_sha256",
        "register_sha256",
        "settings",
    ):
        assert config[key] == manifest[key], key
    assert config["policy"] == {}
    assert config["resumed"] is False
    assert set(config["recipe_sha256"]) == {"intent_readiness"}


def test_resume_skips_scored_items_and_accepts_annotation_edits(
    monkeypatch: Any, tmp_path: Any
) -> None:
    from evals.dataset import io

    calls: list[str] = []
    stop_after = {"n": 2}

    def advise(server: str, item: dict[str, Any]) -> dict[str, Any]:
        if len(calls) >= stop_after["n"]:
            raise KeyboardInterrupt
        calls.append(item["id"])
        return _answers_for(item, SPLIT_USAGE)

    module = _patch(monkeypatch, tmp_path, advise)
    dataset = _dataset(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        module.run_evals("http://127.0.0.1:1", dataset_path=dataset)
    run_id = next((tmp_path / "results").glob("*_run.json")).name.removesuffix(
        "_run.json"
    )
    assert len(calls) == 2
    # an annotation-only edit between interruption and resume is allowed
    items = io.read_items(dataset)
    io.write_items(
        dataset, [items[0].model_copy(update={"rationale": "edited"}), *items[1:]]
    )
    stop_after["n"] = 10
    assert (
        module.run_evals("http://127.0.0.1:1", dataset_path=dataset, resume=run_id) == 0
    )
    trace = next((tmp_path / "results").glob("*_trace.jsonl")).read_text().splitlines()
    assert sorted(json.loads(line)["id"] for line in trace) == [
        "item_000",
        "item_001",
        "item_002",
    ]
    assert calls == ["item_000", "item_001", "item_002"]
    config = json.loads(next((tmp_path / "results").glob("*_results.json")).read_text())
    assert config["config"]["resumed"] is True


def test_resume_refuses_a_changed_setting_or_gold(
    monkeypatch: Any, tmp_path: Any, capsys: Any
) -> None:
    from evals.dataset import io

    def advise(server: str, item: dict[str, Any]) -> dict[str, Any]:
        if item["id"] == "item_001":
            raise KeyboardInterrupt
        return _answers_for(item, SPLIT_USAGE)

    module = _patch(monkeypatch, tmp_path, advise)
    dataset = _dataset(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        module.run_evals("http://127.0.0.1:1", dataset_path=dataset)
    run_id = next((tmp_path / "results").glob("*_run.json")).name.removesuffix(
        "_run.json"
    )
    monkeypatch.setattr(
        module,
        "_health",
        lambda server: {
            "engine": {
                "device": "mps",
                "dtype": "bfloat16",
                "max_length": 10,
                "max_request_length": 5,
            },
            "version": "0.12.0",
        },
    )
    assert (
        module.run_evals("http://127.0.0.1:1", dataset_path=dataset, resume=run_id) == 1
    )
    assert "dtype" in capsys.readouterr().err
    _patch(monkeypatch, tmp_path, advise)
    items = io.read_items(dataset)
    io.write_items(
        dataset,
        [items[0].model_copy(update={"gold_labels": {"intent": "b"}}), *items[1:]],
    )
    assert (
        module.run_evals("http://127.0.0.1:1", dataset_path=dataset, resume=run_id) == 1
    )
    assert "dataset_content_sha256" in capsys.readouterr().err


def test_bare_resume_inherits_the_manifest_filters(
    monkeypatch: Any, tmp_path: Any, capsys: Any
) -> None:
    calls: list[str] = []
    stop_after = {"n": 0}

    def advise(server: str, item: dict[str, Any]) -> dict[str, Any]:
        if len(calls) >= stop_after["n"]:
            raise KeyboardInterrupt
        calls.append(item["id"])
        return _answers_for(item, SPLIT_USAGE)

    module = _patch(monkeypatch, tmp_path, advise)
    dataset = _dataset(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        module.run_evals("http://127.0.0.1:1", dataset_path=dataset, split="dev")
    run_id = next((tmp_path / "results").glob("*_run.json")).name.removesuffix(
        "_run.json"
    )
    stop_after["n"] = 10
    # `--resume RUN_ID` alone continues the run with its recorded split/category
    assert (
        module.run_evals("http://127.0.0.1:1", dataset_path=dataset, resume=run_id) == 0
    )
    trace = next((tmp_path / "results").glob("*_trace.jsonl")).read_text().splitlines()
    assert [json.loads(line)["id"] for line in trace] == ["item_001"]
    # an explicitly different filter is still a mismatch
    assert (
        module.run_evals(
            "http://127.0.0.1:1", dataset_path=dataset, resume=run_id, split="test"
        )
        == 1
    )
    assert "split" in capsys.readouterr().err
