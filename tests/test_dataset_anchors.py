"""Unit tests for per-level rubric anchors (specs/006-benchmark-hygiene, US3)."""

from __future__ import annotations

from evals.dataset import anchors, io
from evals.dataset.records.lint_rule import LintRule
from evals.dataset.scales import SCALES

CRITERIA = {
    ("change_risk", "risk"): ["Negligible", "Low", "Medium", "High"],
    ("effort_approach", "effort"): [
        "Trivial (minutes)",
        "Small (under an hour)",
        "Medium (a few hours)",
        "Large (a day or more)",
    ],
    ("vision_score", "alert_level"): [
        "No alert (calm green)",
        "Low (yellow)",
        "Medium (orange)",
        "High (red)",
    ],
}


def test_every_declared_scale_has_sound_anchors() -> None:
    """Anchors match the question's levels and each differs from its neighbour."""
    for key, criteria in CRITERIA.items():
        scale = SCALES.get(key)
        assert scale is not None, key
        assert anchors.validate_anchors(scale, criteria) == [], key


def test_missing_anchors_are_reported() -> None:
    scale = SCALES[("change_risk", "risk")]
    broken = scale.model_copy(update={"anchors": []})
    assert anchors.validate_anchors(broken, CRITERIA[("change_risk", "risk")])


def test_empty_duplicate_and_short_anchor_lists_are_reported() -> None:
    scale = SCALES[("change_risk", "risk")]
    criteria = CRITERIA[("change_risk", "risk")]
    empty = scale.model_copy(update={"anchors": ["a", "", "c", "d"]})
    problems = anchors.validate_anchors(empty, criteria)
    assert any("empty" in problem for problem in problems)
    duplicates = scale.model_copy(update={"anchors": ["a", "b", "b", "d"]})
    assert any(
        "share" in problem for problem in anchors.validate_anchors(duplicates, criteria)
    )
    short = scale.model_copy(update={"anchors": ["a", "b"]})
    assert any(
        "expected 4" in problem for problem in anchors.validate_anchors(short, criteria)
    )


def test_the_lint_enforces_anchors(monkeypatch) -> None:
    """A blanked anchor produces an enforced ``scale-anchored`` finding."""
    from evals.dataset import lint

    items = [i for i in io.read_items(io.DATASET_PATH) if i.category == "change_risk"]
    scale = SCALES[("change_risk", "risk")]
    broken = scale.model_copy(update={"anchors": ["same", "", "same", "d"]})
    monkeypatch.setattr(lint, "scale_for", lambda *args, **kwargs: broken)
    found = [
        finding
        for finding in lint.scale_rules("change_risk", items)
        if finding.rule is LintRule.scale_anchored
    ]
    assert found, "a blanked anchor must fail the lint"
    assert all(finding.enforced for finding in found)
