"""``metrics.aggregate`` additions from specs/004 Phase 0: headline scope,
capability, risk, tokens, consistency, by-source-kind, and tiers."""

from __future__ import annotations

import pytest
from evals import metrics
from evals.dataset import recipes
from evals.dataset.records.family import Family
from evals.dataset.records.lint_mode import LintMode

CHOICE_SPEC = {
    "type": "choice",
    "instructions": "Which part of the system should handle this?",
    "criteria": {"api": "HTTP", "storage": "DB"},
}
NOUL_SPEC = {"type": "noul", "instructions": "Is red dominant?"}


def _result(
    item_id: str,
    category: str,
    *,
    correct: bool = True,
    qtype: str = "choice",
    **annotations: object,
) -> dict[str, object]:
    if qtype == "choice":
        spec, gold = CHOICE_SPEC, "api"
        answer = {
            "type": "choice",
            "choice": "api" if correct else "storage",
            "confidence": 0.9,
            "probabilities": {"api": 0.9, "storage": 0.1}
            if correct
            else {"api": 0.1, "storage": 0.9},
        }
        qid = "owner"
    else:
        spec, gold = NOUL_SPEC, True
        answer = {"type": "noul", "noul": 0.9 if correct else 0.1}
        qid = "dominant_red"
    item = {
        "id": item_id,
        "category": category,
        "split": "test",
        "questions": {qid: spec},
        "gold_labels": {qid: gold},
    }
    scored = metrics.score_item(item, {qid: answer})
    scored.update(annotations)
    return scored


def test_aggregate_headline_excludes_capability_recipes() -> None:
    results = [
        _result("r1", "routing"),
        _result("r2", "routing", correct=False),
        _result("v1", "vision_noul", qtype="noul"),
        _result("v2", "vision_noul", qtype="noul"),
    ]
    summary = metrics.aggregate(results)
    assert summary["overall"]["items"] == 2
    assert summary["overall"]["questions"] == 2
    assert summary["overall"]["accuracy"] == pytest.approx(0.5)
    capability = summary["capability"]
    assert capability["items"] == 2
    assert capability["questions"] == 2
    assert capability["accuracy"] == pytest.approx(1.0)
    assert set(capability["categories"]) == {"vision_noul"}
    assert "accuracy_ci" in capability
    assert summary["categories"]["vision_noul"]["items"] == 2
    assert summary["risk"] == {}
    assert summary["tokens"] is None
    assert summary["consistency"] == {}
    assert summary["by_source_kind"] == {}
    assert summary["tiers"] is None


def test_aggregate_without_capability_recipes_reports_none() -> None:
    summary = metrics.aggregate([_result("r1", "routing")])
    assert summary["capability"] is None


def test_aggregate_tokens_bins_state_lengths() -> None:
    results = [
        _result(
            "r1",
            "routing",
            tokens={"total": 200, "state": 30, "fixed": 170, "media": 0},
        ),
        _result(
            "r2",
            "routing",
            correct=False,
            tokens={"total": 2200, "state": 2000, "fixed": 200, "media": 0},
        ),
    ]
    tokens = metrics.aggregate(results)["tokens"]
    assert tokens["median_state"] == pytest.approx(1015.0)
    assert tokens["max_state"] == 2000
    assert sum(b["n"] for b in tokens["state_bins"]) == 2
    assert all(
        {"low", "high", "n", "accuracy", "brier"} <= set(b)
        for b in tokens["state_bins"]
    )


def test_aggregate_reports_consistency_over_variant_groups() -> None:
    results = [
        _result("p", "routing"),
        _result(
            "p-a",
            "routing",
            source_kind="perturbed",
            parent_id="p",
            perturbation="paraphrase",
        ),
        _result(
            "p-b",
            "routing",
            correct=False,
            source_kind="perturbed",
            parent_id="p",
            perturbation="format",
        ),
        _result("q", "routing"),
        _result(
            "q-a",
            "routing",
            source_kind="perturbed",
            parent_id="q",
            perturbation="paraphrase",
        ),
        _result(
            "q-x",
            "routing",
            source_kind="perturbed",
            parent_id="q",
            perturbation="noise",
        ),
    ]
    consistency = metrics.aggregate(results)["consistency"]
    assert consistency["routing"] == {"groups": 2, "agreement": pytest.approx(0.5)}
    assert metrics.aggregate([_result("r1", "routing")])["consistency"] == {}


def test_aggregate_reports_accuracy_by_source_kind_only_for_mixed_recipes() -> None:
    mixed = [
        _result("a1", "routing", source_kind="authored"),
        _result("i1", "routing", correct=False, source_kind="imported"),
        _result("i2", "routing", source_kind="imported"),
    ]
    by_kind = metrics.aggregate(mixed)["by_source_kind"]["routing"]
    assert by_kind["authored"] == {"items": 1, "accuracy": 1.0, "item_accuracy": 1.0}
    assert by_kind["imported"]["items"] == 2
    assert by_kind["imported"]["accuracy"] == pytest.approx(0.5)
    single = [_result("a1", "routing", source_kind="authored")]
    assert metrics.aggregate(single)["by_source_kind"] == {}


def test_aggregate_reports_non_easy_accuracy() -> None:
    results = [
        _result("e1", "routing", tier="easy"),
        _result("h1", "routing", tier=None),
        _result("h2", "routing", correct=False, tier=None),
    ]
    tiers = metrics.aggregate(results)["tiers"]
    assert tiers["easy_items"] == 1
    assert tiers["easy_questions"] == 1
    assert tiers["non_easy"]["items"] == 2
    assert tiers["non_easy"]["accuracy"] == pytest.approx(0.5)
    assert "accuracy_ci" in tiers["non_easy"]


def test_aggregate_reports_risk_for_flagged_recipes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    risky = recipes.RECIPES["routing"].model_copy(
        update={
            "risk": True,
            "family": Family.risk_trio,
            "lint": LintMode.report,
            "dangerous_options": {"owner": frozenset({"storage"})},
        }
    )
    monkeypatch.setitem(recipes.RECIPES, "routing", risky)
    results = [_result("r1", "routing"), _result("r2", "routing", correct=False)]
    risk = metrics.aggregate(results)["risk"]
    assert set(risk) == {"routing"}
    assert {"dangerous_recall", "missed_dangers", "bar", "met"} <= set(risk["routing"])
