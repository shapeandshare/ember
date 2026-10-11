"""``ember eval report --compare``: two runs are comparable when they scored the
same dataset *version* (content hash), not the same file bytes.
"""

from __future__ import annotations

from typing import Any

from evals.eval import report_compare, report_evals


def _run(run_id: str, *, content: str | None, file_hash: str) -> dict[str, Any]:
    config: dict[str, Any] = {
        "run_id": run_id,
        "git_hash": "abc1234",
        "dataset": "clef-flash.jsonl",
        "dataset_sha256": file_hash,
        "split": None,
        "category": None,
    }
    if content is not None:
        config["dataset_content_sha256"] = content
    return {
        "config": config,
        "summary": {
            "overall": {"accuracy": 0.8, "item_accuracy": 0.7},
            "questions": {"intent": {"accuracy": 0.8}},
        },
    }


def test_compare_accepts_annotation_only_differences() -> None:
    a = _run("a", content="c" * 64, file_hash="1" * 64)
    b = _run("b", content="c" * 64, file_hash="2" * 64)
    assert "Warning" not in report_compare.render_compare(a, b)


def test_compare_warns_when_the_dataset_version_differs() -> None:
    a = _run("a", content="c" * 64, file_hash="1" * 64)
    b = _run("b", content="d" * 64, file_hash="1" * 64)
    assert "different item sets" in report_compare.render_compare(a, b)


def test_compare_falls_back_to_the_file_hash_for_pre_phase_0_runs() -> None:
    same = report_compare.render_compare(
        _run("a", content=None, file_hash="1" * 64),
        _run("b", content=None, file_hash="1" * 64),
    )
    differs = report_compare.render_compare(
        _run("a", content=None, file_hash="1" * 64),
        _run("b", content=None, file_hash="2" * 64),
    )
    assert "Warning" not in same
    assert "Warning" in differs


def test_render_names_the_dataset_version_when_recorded() -> None:
    config = {
        "run_id": "a",
        "model": "flash",
        "git_hash": "abc1234",
        "dataset": "clef-flash.jsonl",
        "dataset_sha256": "1" * 64,
        "dataset_content_sha256": "c" * 64,
        "split": None,
        "n_items": 1,
        "n_errors": 0,
    }
    summary = {
        "overall": {
            "items": 1,
            "questions": 1,
            "accuracy": 1.0,
            "accuracy_ci": [1.0, 1.0],
            "item_accuracy": 1.0,
        },
        "choice": None,
        "noul": None,
        "score": None,
        "questions": {},
        "categories": {},
        "misses": [],
    }
    text = report_evals.render({"config": config, "summary": summary})
    assert f"version `{'c' * 12}`" in text
    assert "1" * 12 not in text
