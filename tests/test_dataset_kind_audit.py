"""Unit tests for the kind audit (specs/006-benchmark-hygiene, US4)."""

from __future__ import annotations

import json

import pytest
from evals.dataset import io, kinds
from evals.dataset.lint import kind_shares
from evals.dataset.records.item import Item


def test_audit_counts_every_item_and_names_the_untagged() -> None:
    items = io.read_items(io.DATASET_PATH)
    report = kinds.audit(items)
    assert sum(entry["items"] for entry in report.values()) == len(items)
    for entry in report.values():
        tagged = sum(
            count for kind, count in entry["kinds"].items() if kind != "untagged"
        )
        assert entry["untagged"] == entry["items"] - tagged


def test_audit_gaps_are_exactly_the_lints_kind_share_findings() -> None:
    """The audit never re-implements the rule; it reports the lint's gaps."""
    items = io.read_items(io.DATASET_PATH)
    by_recipe: dict[str, list[Item]] = {}
    for item in items:
        by_recipe.setdefault(item.category, []).append(item)
    expected = sum(
        len(kind_shares(category, rows, enforced=False))
        for category, rows in by_recipe.items()
    )
    report = kinds.audit(items)
    assert sum(len(entry["gaps"]) for entry in report.values()) == expected


def test_main_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = kinds.main(["--dataset", str(io.DATASET_PATH), "--json"])
    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed
    assert all("untagged" in entry for entry in parsed.values())
