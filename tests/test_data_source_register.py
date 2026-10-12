"""The data-source register and the example-secret list (specs/004 FR-039 to FR-045)."""

from __future__ import annotations

import json

import pytest
from evals.dataset import register
from evals.dataset.records.item import Item
from evals.dataset.records.register_row import RegisterRow
from evals.dataset.records.verdict import Verdict
from pydantic import ValidationError

HASH64 = "e" * 64
SHA40 = "a" * 40


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "example-source",
        "name": "Example source",
        "urls": [{"url": "https://example.org/data", "read_on": "2026-10-10"}],
        "licence": {
            "reading": "MIT",
            "spdx": "MIT",
            "read_at": "https://example.org/LICENSE",
            "read_on": "2026-10-10",
            "class": "permissive",
        },
        "verdict": "candidate",
        "reason": "Permissive and downloadable.",
        "feeds": ["routing"],
    }
    base.update(overrides)
    return base


def _used(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "verdict": "used",
        "snapshot": {"version": "v1", "sha256": HASH64, "retrieved_on": "2026-10-10"},
        "mirror": {
            "location": "s3://ember-mirrors/example-v1.tar",
            "sha256": HASH64,
            "public": False,
        },
        "transformation": "mapped `label` onto `owner`",
        "items_imported": 1,
    }
    base.update(overrides)
    return _row(**base)


def test_row_validates_with_the_minimum_fields() -> None:
    row = RegisterRow.model_validate(_row())
    assert row.verdict is Verdict.candidate
    assert row.items_imported == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"urls": []},
        {"reason": ""},
        {"id": "Bad Id"},
        {
            "licence": {
                "reading": "MIT",
                "read_at": "ftp://x",
                "read_on": "2026-10-10",
                "class": "permissive",
            }
        },
    ],
)
def test_row_rejects_incomplete_records(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RegisterRow.model_validate(_row(**overrides))


def test_used_rows_need_snapshot_mirror_and_transformation() -> None:
    RegisterRow.model_validate(_used())
    with pytest.raises(ValidationError, match="snapshot, mirror, transformation"):
        RegisterRow.model_validate(_row(verdict="used"))
    with pytest.raises(ValidationError, match="mirror hash"):
        RegisterRow.model_validate(
            _used(mirror={"location": "x", "sha256": "f" * 64, "public": False})
        )


def test_only_used_rows_may_have_imported_items() -> None:
    with pytest.raises(ValidationError, match="only a used row"):
        RegisterRow.model_validate(_row(items_imported=3))


@pytest.mark.parametrize("licence_class", ["non_commercial", "research_only", "gated"])
def test_excluding_licence_classes_force_the_excluded_verdict(
    licence_class: str,
) -> None:
    licence = {**_row()["licence"], "class": licence_class}  # type: ignore[dict-item]
    with pytest.raises(ValidationError, match="excluded"):
        RegisterRow.model_validate(_row(licence=licence))
    RegisterRow.model_validate(_row(licence=licence, verdict="excluded"))


def test_share_alike_used_rows_need_attribution() -> None:
    licence = {**_row()["licence"], "class": "share_alike"}  # type: ignore[dict-item]
    with pytest.raises(ValidationError, match="attribution"):
        RegisterRow.model_validate(_used(licence=licence))
    RegisterRow.model_validate(
        _used(licence=licence, attribution="CC BY-SA 4.0, Example")
    )


def test_custom_permissive_used_rows_need_permission() -> None:
    licence = {**_row()["licence"], "class": "custom_permissive"}  # type: ignore[dict-item]
    with pytest.raises(ValidationError, match="permission"):
        RegisterRow.model_validate(_used(licence=licence))
    RegisterRow.model_validate(
        _used(licence=licence, permission="LICENSES.md §Exception (commit 422648d9)")
    )


def _item(item_id: str, source: dict[str, object]) -> Item:
    return Item.model_validate(
        {
            "id": item_id,
            "category": "routing",
            "split": "dev",
            "state": "x",
            "questions": {
                "owner": {
                    "type": "choice",
                    "instructions": "?",
                    "criteria": {"api": "a"},
                }
            },
            "gold_labels": {"owner": "api"},
            "rationale": "r",
            "source": source,
        }
    )


def test_validate_cross_checks_items_against_rows() -> None:
    used = RegisterRow.model_validate(_used())
    candidate = RegisterRow.model_validate(_row(id="other"))
    imported = _item(
        "i1", {"kind": "imported", "register_row": "example-source", "record_id": "1"}
    )
    assert register.validate([used, candidate], [imported]) == []
    stray = _item("i2", {"kind": "imported", "register_row": "other", "record_id": "1"})
    problems = register.validate([used, candidate], [imported, stray])
    assert any("is candidate" in p for p in problems)
    assert any("items_imported is 0 but 1" in p for p in problems)
    assert any("items_imported is 1 but 0" in p for p in register.validate([used], []))


def test_validate_cross_checks_mined_items_against_rows() -> None:
    used = RegisterRow.model_validate(_used())
    mined = _item(
        "m1",
        {
            "kind": "mined",
            "artefact": "docs/vault/Decisions/a.md",
            "commit": SHA40,
            "register_row": "example-source",
        },
    )
    assert register.validate([used], [mined]) == []
    stray = _item(
        "m2",
        {
            "kind": "mined",
            "artefact": "docs/vault/Decisions/b.md",
            "commit": SHA40,
            "register_row": "other",
        },
    )
    problems = register.validate([used], [stray])
    assert any("does not exist" in p for p in problems)
    assert any("items_imported is 1 but 0" in p for p in problems)


# ###########################################################################
# The committed register (first survey)
# ###########################################################################

CANDIDATE_IDS = {
    "nist-juliet",
    "cvefixes",
    "apachejit",
    "swe-bench",
    "agentdojo",
    "deepset-prompt-injections",
    "ragtruth",
    "scancode-licensedb",
    "nvidia-aegis-2",
    "typesafe-evalsafe-security-incidents",
}
EXCLUDED_IDS = {
    "anli",
    "r-judge",
    "agentharm",
    "commitbench",
    "beavertails",
    "wildguardmix",
    "toxigen",
    "secretbench",
    "bipia",
    "gpqa",
}


def test_committed_register_validates_with_the_expected_used_row() -> None:
    from evals.dataset import io

    rows = register.load()
    ids = {row.id for row in rows}
    assert CANDIDATE_IDS <= ids, CANDIDATE_IDS - ids
    assert EXCLUDED_IDS <= ids, EXCLUDED_IDS - ids
    used = {row.id for row in rows if row.verdict is Verdict.used}
    assert used == {"oldgrowth-vault"}
    row = next(candidate for candidate in rows if candidate.id == "oldgrowth-vault")
    assert row.permission
    assert row.snapshot is not None
    assert row.mirror is not None
    assert row.mirror.sha256 == row.snapshot.sha256
    assert all(
        row.verdict is Verdict.excluded for row in rows if row.id in EXCLUDED_IDS
    )
    assert all(
        row.verdict is not Verdict.excluded for row in rows if row.id in CANDIDATE_IDS
    )
    assert len(rows) >= 60
    assert register.validate(rows, io.read_items(io.DATASET_PATH)) == []


def test_committed_register_has_a_schema_version_and_date() -> None:
    data = json.loads(register.REGISTER_PATH.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["recorded_on"] == "2026-10-10"


def test_committed_example_secrets_validate() -> None:
    entries = register.load_example_secrets()
    assert {e.value for e in entries} >= {"AKIAIOSFODNN7EXAMPLE"}
    assert all(e.url.startswith("https://") for e in entries)
