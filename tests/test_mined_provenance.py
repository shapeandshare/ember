"""Mined-source provenance: the permissionless (MIT) mapping (specs/007 T034)."""

from __future__ import annotations

from evals.dataset import register
from evals.dataset.records.item import Item
from evals.dataset.records.register_row import RegisterRow

HASH64 = "e" * 64


def _permissive_used_row() -> RegisterRow:
    return RegisterRow.model_validate(
        {
            "id": "ember-vault",
            "name": "ember vault",
            "urls": [
                {
                    "url": "https://github.com/shapeandshare/ember",
                    "read_on": "2026-10-12",
                }
            ],
            "licence": {
                "reading": "MIT",
                "spdx": "MIT",
                "read_at": "https://github.com/shapeandshare/ember/blob/main/LICENSE",
                "read_on": "2026-10-12",
                "class": "permissive",
            },
            "verdict": "used",
            "reason": "MIT: redistribution with attribution.",
            "snapshot": {
                "version": "v1",
                "sha256": HASH64,
                "retrieved_on": "2026-10-12",
            },
            "mirror": {
                "location": "shapeandshare/ember @ v1",
                "sha256": HASH64,
                "public": True,
            },
            "transformation": "notes sampled into tag_assignment items",
            "items_imported": 1,
            "attribution": "ember (MIT)",
        }
    )


def _mined_item() -> Item:
    return Item.model_validate(
        {
            "id": "tag_assignment-vault-x",
            "category": "tag_assignment",
            "split": "dev",
            "state": "x",
            "questions": {
                "type/decision": {"type": "noul", "instructions": "?"}
            },
            "gold_labels": {"type/decision": True},
            "rationale": "r",
            "source": {
                "kind": "mined",
                "artefact": "vault/x.md",
                "commit": "a" * 40,
                "register_row": "ember-vault",
            },
        }
    )


def test_a_permissive_used_row_needs_no_permission_field() -> None:
    row = _permissive_used_row()
    assert row.permission is None
    assert row.verdict.value == "used"


def test_a_mined_item_validates_against_a_permissive_row() -> None:
    assert register.validate([_permissive_used_row()], [_mined_item()]) == []
