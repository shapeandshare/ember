"""Leaderboard model, specs/004 Phase 0: one table per dataset version,
``(model, deployment, settings)`` rows, per-recipe columns assembled from the
latest run that scored each recipe, incomplete rows, and pass-through of the
capability, risk, and tier blocks.

Shares the synthetic ``model.json`` factory of ``tests/test_leaderboard.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from evals import leaderboard

from tests.test_leaderboard import _run


def _versioned(
    *,
    run_id: str,
    run_at: str,
    content: str,
    recipes: dict[str, str],
    categories: dict[str, tuple[int, float]],
    accuracy: float = 0.8,
    dtype: str = "float16",
    settings: dict[str, Any] | None = None,
    deployment_label: str = "Local (Apple Silicon, MPS)",
    capability: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    tiers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = _run(
        run_id=run_id,
        run_at=run_at,
        model="clef-flash",
        model_spec={"name": "flash"},
        dtype=dtype,
        deployment_label=deployment_label,
        accuracy=accuracy,
    )
    run["meta"].update(
        dataset_content_sha256=content,
        recipe_sha256=recipes,
        settings=settings
        or {"dtype": dtype, "max_length": 262144, "max_request_length": 24576},
        dataset={"sha256": "f" * 64},
    )
    run["summary"]["categories"] = {
        category: {"items": items, "item_accuracy": acc, "accuracy": acc}
        for category, (items, acc) in categories.items()
    }
    run["summary"]["questions"] = {
        f"{category}_q": {
            "type": "choice",
            "category": category,
            "n": items,
            "accuracy": acc,
        }
        for category, (items, acc) in categories.items()
    }
    run["summary"]["capability"] = capability
    run["summary"]["risk"] = risk or {}
    run["summary"]["tiers"] = tiers
    return run


ALL_HEADLINE = {
    c: f"h-{c}"
    for c in (
        "intent_readiness",
        "failure_triage",
        "change_risk",
        "routing",
        "effort_approach",
        "tag_assignment",
    )
}
ALL_CATEGORIES = {c: (10, 0.8) for c in ALL_HEADLINE}


def test_versions_are_keyed_by_content_hash_newest_first() -> None:
    old = _versioned(
        run_id="old",
        run_at="2026-10-01 00:00 UTC",
        content="a" * 64,
        recipes=ALL_HEADLINE,
        categories=ALL_CATEGORIES,
    )
    new = _versioned(
        run_id="new",
        run_at="2026-10-10 00:00 UTC",
        content="b" * 64,
        recipes={**ALL_HEADLINE, "routing": "h-routing-2"},
        categories=ALL_CATEGORIES,
    )
    board = leaderboard.build([old, new])
    assert [v["dataset_content_sha256"] for v in board["versions"]] == [
        "b" * 64,
        "a" * 64,
    ]
    assert board["versions"][0]["newest"] is True
    assert [row["run_id"] for row in board["rows"]] == ["new"]


def test_the_current_version_leaderboard_carries_tag_assignment() -> None:
    """specs/007's phase gate: tag_assignment renders for the current version."""
    from evals.dataset import hashes, io
    from evals.leaderboard import build

    benchmark = Path(__file__).resolve().parents[1] / "benchmark"
    models = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(benchmark.glob("*/model.json"))
    ]
    current = hashes.dataset_content_sha256(io.read_items(io.DATASET_PATH))
    board = build(models)
    version = next(
        entry
        for entry in board["versions"]
        if entry.get("dataset_content_sha256") == current
    )
    assert any("tag_assignment" in row["recipes"] for row in version["rows"])


def test_rows_assemble_recipes_from_the_latest_matching_run_in_a_group() -> None:
    full = _versioned(
        run_id="full",
        run_at="2026-10-01 00:00 UTC",
        content="a" * 64,
        recipes=ALL_HEADLINE,
        categories=ALL_CATEGORIES,
        accuracy=0.8,
    )
    partial = _versioned(
        run_id="partial",
        run_at="2026-10-05 00:00 UTC",
        content="a" * 64,
        recipes={"routing": "h-routing"},
        categories={"routing": (10, 1.0)},
        accuracy=1.0,
    )
    board = leaderboard.build([full, partial])
    [row] = board["versions"][0]["rows"]
    assert row["recipes"]["routing"]["run_id"] == "partial"
    assert row["recipes"]["change_risk"]["run_id"] == "full"
    assert row["incomplete"] is False
    assert row["headline"] is not None
    assert row["run_id"] == "partial"
    assert row["headline"]["accuracy"] == pytest.approx(
        round((5 * 10 * 0.8 + 10 * 1.0) / 60, 4)
    )


def test_rows_are_incomplete_until_every_headline_recipe_is_scored() -> None:
    partial = _versioned(
        run_id="partial",
        run_at="2026-10-05 00:00 UTC",
        content="a" * 64,
        recipes={"routing": "h-routing"},
        categories={"routing": (10, 1.0)},
    )
    [row] = leaderboard.build([partial])["versions"][0]["rows"]
    assert row["incomplete"] is True
    assert row["headline"] is None
    assert set(row["recipes"]) == {"routing"}


def test_settings_split_groups_and_hashes_split_versions() -> None:
    fp16 = _versioned(
        run_id="fp16",
        run_at="2026-10-01 00:00 UTC",
        content="a" * 64,
        recipes=ALL_HEADLINE,
        categories=ALL_CATEGORIES,
    )
    capped = _versioned(
        run_id="capped",
        run_at="2026-10-02 00:00 UTC",
        content="a" * 64,
        recipes=ALL_HEADLINE,
        categories=ALL_CATEGORIES,
        settings={"dtype": "float16", "max_length": 262144, "max_request_length": 4096},
    )
    board = leaderboard.build([fp16, capped])
    assert len(board["versions"]) == 1
    assert {row["run_id"] for row in board["versions"][0]["rows"]} == {"fp16", "capped"}


def test_legacy_runs_without_a_content_hash_form_their_own_version() -> None:
    legacy = _run(run_id="legacy", run_at="2026-09-01 00:00 UTC", model="clef-flash")
    legacy["meta"]["dataset"] = {"sha256": "c" * 64}
    versioned = _versioned(
        run_id="v",
        run_at="2026-10-10 00:00 UTC",
        content="a" * 64,
        recipes=ALL_HEADLINE,
        categories=ALL_CATEGORIES,
    )
    board = leaderboard.build([legacy, versioned])
    keys = [v["dataset_content_sha256"] for v in board["versions"]]
    assert keys == ["a" * 64, "c" * 64]
    [legacy_row] = board["versions"][1]["rows"]
    assert legacy_row["run_id"] == "legacy"
    assert legacy_row["headline"]["accuracy"] == 0.80


def test_rows_pass_through_capability_risk_tiers_and_single_rater() -> None:
    run = _versioned(
        run_id="r",
        run_at="2026-10-10 00:00 UTC",
        content="a" * 64,
        recipes=ALL_HEADLINE,
        categories=ALL_CATEGORIES,
        capability={
            "items": 32,
            "questions": 32,
            "accuracy": 1.0,
            "accuracy_ci": [1.0, 1.0],
            "categories": {},
        },
        risk={
            "routing": {
                "dangerous_recall_at_threshold": 0.9,
                "missed_dangers": 1,
                "met": False,
            }
        },
        tiers={
            "easy_items": 3,
            "easy_questions": 3,
            "non_easy": {"items": 7, "questions": 7, "accuracy": 0.7},
        },
    )
    [row] = leaderboard.build([run])["versions"][0]["rows"]
    assert row["capability"]["accuracy"] == 1.0
    assert row["risk"]["routing"]["missed_dangers"] == 1
    assert row["tiers"] == {"non_easy_accuracy": 0.7}
    assert row["single_rater"] is True


def test_assembled_row_reports_the_latency_of_its_newest_contributing_run() -> None:
    full = _versioned(
        run_id="full",
        run_at="2026-10-01 00:00 UTC",
        content="a" * 64,
        recipes=ALL_HEADLINE,
        categories=ALL_CATEGORIES,
    )
    full["latency"] = {"p50": 600.0, "p95": 800.0}
    partial = _versioned(
        run_id="partial",
        run_at="2026-10-05 00:00 UTC",
        content="a" * 64,
        recipes={"routing": "h-routing"},
        categories={"routing": (10, 1.0)},
    )
    partial["latency"] = {"p50": 500.0, "p95": 650.0}
    [row] = leaderboard.build([full, partial])["versions"][0]["rows"]
    assert row["run_id"] == "partial"
    assert row["latency_p50"] == 500.0


def test_version_recipe_hashes_come_from_the_newest_run_that_recorded_them() -> None:
    older = _versioned(
        run_id="older",
        run_at="2026-10-01 00:00 UTC",
        content="a" * 64,
        recipes={**ALL_HEADLINE, "routing": "h-routing-old"},
        categories=ALL_CATEGORIES,
        deployment_label="Remote hosted (GPU, CUDA)",
    )
    newer = _versioned(
        run_id="newer",
        run_at="2026-10-05 00:00 UTC",
        content="a" * 64,
        recipes=ALL_HEADLINE,
        categories=ALL_CATEGORIES,
    )
    board = leaderboard.build([newer, older])
    by_id = {row["run_id"]: row for row in board["versions"][0]["rows"]}
    assert by_id["newer"]["recipes"]["routing"]["recipe_sha256"] == "h-routing"
    # the older deployment recorded a different routing hash: its column is missing
    assert "routing" not in by_id["older"]["recipes"]
    assert by_id["older"]["incomplete"] is True
