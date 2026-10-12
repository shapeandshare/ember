"""Unit tests for the dataset tooling package (``evals/dataset``)."""

from __future__ import annotations

import pytest
from evals.dataset.records.compliance_framework import ComplianceFramework
from evals.dataset.records.dangerous_end import DangerousEnd
from evals.dataset.records.family import Family
from evals.dataset.records.item_kind import ItemKind
from evals.dataset.records.licence_class import LicenceClass
from evals.dataset.records.lint_mode import LintMode
from evals.dataset.records.lint_rule import LintRule
from evals.dataset.records.recipe_spec import RecipeSpec
from evals.dataset.records.scale import Scale
from evals.dataset.records.source_kind import SourceKind
from evals.dataset.records.split import Split
from evals.dataset.records.verdict import Verdict
from pydantic import ValidationError

# ###########################################################################
# Enums (data-model.md)
# ###########################################################################


@pytest.mark.parametrize(
    ("enum", "values"),
    [
        (DangerousEnd, ["low", "high", "none"]),
        (
            Family,
            [
                "coding",
                "vision",
                "mined_vault",
                "risk_trio",
                "harm_security",
                "spec_kit",
                "grounding",
                "long_tier",
                "boundary",
                "memory_loop",
                "low_priority",
                "integration",
            ],
        ),
        (LintMode, ["report", "enforce"]),
        (
            ComplianceFramework,
            [
                "owasp_llm_top10",
                "mitre_atlas",
                "nist_ai_rmf",
                "eu_ai_act",
                "iso_42001",
                "enkrypt",
            ],
        ),
        (
            SourceKind,
            [
                "authored",
                "mined",
                "captured",
                "perturbed",
                "templated",
                "drafted",
                "imported",
            ],
        ),
        (
            ItemKind,
            [
                "positive",
                "negative",
                "control",
                "hard_negative",
                "near_miss",
                "adversarial",
                "insufficient_context",
                "variant",
                "long_tier",
            ],
        ),
        (Split, ["dev", "test"]),
        (Verdict, ["candidate", "conditional", "excluded", "unconfirmed", "used"]),
        (
            LicenceClass,
            [
                "permissive",
                "share_alike",
                "custom_permissive",
                "non_commercial",
                "research_only",
                "gated",
                "composite",
                "unconfirmed",
            ],
        ),
        (
            LintRule,
            [
                "size-target",
                "label-in-both-splits",
                "kind-shares",
                "template-share",
                "scale-declared",
                "dangerous-set-declared",
                "scale-anchored",
                "source-resolves",
                "family-split",
                "split-pinned",
                "near-duplicate-gold",
                "no-live-secret",
            ],
        ),
    ],
)
def test_enum_exposes_exactly_the_listed_values(enum: type, values: list[str]) -> None:
    assert [member.value for member in enum] == values


# ###########################################################################
# Scale
# ###########################################################################


def _scale(**overrides: object) -> Scale:
    base: dict[str, object] = {
        "category": "change_risk",
        "question": "risk",
        "quantity": "risk of shipping unreviewed",
        "low": "Negligible",
        "high": "High",
        "dangerous_end": DangerousEnd.high,
        "dangerous_from": 2,
        "since": "1" * 64,
    }
    base.update(overrides)
    return Scale(**base)  # type: ignore[arg-type]


def test_scale_legend_names_both_poles_with_their_indices() -> None:
    assert _scale().legend(levels=4) == "0 Negligible → 3 High"


def test_scale_requires_dangerous_from_when_an_end_is_dangerous() -> None:
    with pytest.raises(ValidationError):
        _scale(dangerous_from=None)


def test_scale_rejects_dangerous_from_when_no_end_is_dangerous() -> None:
    with pytest.raises(ValidationError):
        _scale(dangerous_end=DangerousEnd.none, dangerous_from=1)
    assert (
        _scale(dangerous_end=DangerousEnd.none, dangerous_from=None).dangerous_from
        is None
    )


def test_scale_is_frozen() -> None:
    with pytest.raises(ValidationError):
        _scale().low = "Trivial"  # type: ignore[misc]


# ###########################################################################
# RecipeSpec
# ###########################################################################


def _recipe(**overrides: object) -> RecipeSpec:
    base: dict[str, object] = {
        "category": "routing",
        "title": "Routing and ownership",
        "when": "When an error needs an owner.",
        "state": "The error message.",
        "decides": "Which part of the system should handle it.",
        "family": Family.coding,
        "phase": 0,
    }
    base.update(overrides)
    return RecipeSpec(**base)  # type: ignore[arg-type]


def test_recipe_spec_defaults_are_the_grandfathered_ones() -> None:
    spec = _recipe()
    assert spec.risk is False
    assert spec.compliance == ()
    assert spec.policy_slot is False
    assert spec.dangerous_options == {}
    assert spec.lint is LintMode.report
    assert spec.exemptions == {}


@pytest.mark.parametrize(
    ("family", "headline"),
    [
        (Family.coding, True),
        (Family.risk_trio, True),
        (Family.vision, False),
        (Family.integration, False),
    ],
)
def test_recipe_spec_headline_excludes_vision_and_integration(
    family: Family, headline: bool
) -> None:
    assert _recipe(family=family).headline is headline


# ###########################################################################
# Source and Item
# ###########################################################################

HASH64 = "a" * 64
SHA40 = "b" * 40


def _source(kind: str, **refs: object) -> dict[str, object]:
    return {"kind": kind, **refs}


@pytest.mark.parametrize(
    "payload",
    [
        _source("authored", dataset_version=HASH64),
        _source("authored", dataset_version=HASH64, note="reproduces a worked example"),
        _source("mined", artefact="vault/decisions/x.md", commit=SHA40),
        _source("captured", session_id="ses_1", redaction_sha256=HASH64),
        _source("perturbed", parent_id="risk_001", perturbation="paraphrase"),
        _source("templated", family="cmd-x-target", template_version="1"),
        _source("drafted", draft_id="draft-7", adjudicated=True),
        _source("imported", register_row="nist-juliet", record_id="CWE78_1"),
    ],
)
def test_source_accepts_each_kind_with_its_references(
    payload: dict[str, object],
) -> None:
    from evals.dataset.records.source import Source

    assert Source(**payload).kind.value == payload["kind"]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "payload",
    [
        _source("authored"),
        _source("authored", dataset_version="short"),
        _source("mined", artefact="vault/x.md"),
        _source("mined", artefact="vault/x.md", commit="nothex"),
        _source("captured", session_id="ses_1"),
        _source("perturbed", parent_id="risk_001"),
        _source("templated", family="f"),
        _source("drafted", draft_id="d", adjudicated=False),
        _source("imported", register_row="r"),
        _source("mined", artefact="vault/x.md", commit=SHA40, note="foreign field"),
        _source("authored", dataset_version=HASH64, parent_id="foreign"),
    ],
)
def test_source_rejects_missing_or_foreign_references(
    payload: dict[str, object],
) -> None:
    from evals.dataset.records.source import Source

    with pytest.raises(ValidationError):
        Source(**payload)  # type: ignore[arg-type]


def _item(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "routing_900",
        "category": "routing",
        "split": "dev",
        "state": "KeyError in api/handlers.py",
        "questions": {
            "owner": {
                "type": "choice",
                "instructions": "Which part of the system should handle this?",
                "criteria": {"api": "HTTP", "storage": "DB"},
            }
        },
        "gold_labels": {"owner": "api"},
        "rationale": "The trace names an HTTP handler.",
        "source": _source("authored", dataset_version=HASH64),
    }
    base.update(overrides)
    return base


def test_item_validates_and_has_phase_0_defaults() -> None:
    from evals.dataset.records.item import Item

    item = Item(**_item())  # type: ignore[arg-type]
    assert item.kind is None
    assert item.tier is None
    assert item.acted_differs is False
    assert item.second_review is False
    assert item.split is Split.dev


@pytest.mark.parametrize(
    "overrides",
    [
        {"rationale": "  "},
        {"gold_labels": {"other": "api"}},
        {"gold_labels": {}},
        {"split": "holdout"},
        {"tier": "hard"},
    ],
)
def test_item_rejects_inconsistent_records(overrides: dict[str, object]) -> None:
    from evals.dataset.records.item import Item

    with pytest.raises(ValidationError):
        Item(**_item(**overrides))  # type: ignore[arg-type]
