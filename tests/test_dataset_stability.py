"""Unit tests for the stability round tool (specs/006-benchmark-hygiene, US1).

The red phase: these import ``evals.dataset.stability`` before it exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals.dataset import io, stability
from evals.dataset.records.stability_round import StabilityRound
from evals.dataset.stability import StabilityError

SCOPE = ("change_risk", "effort_approach")


def _scoped_items(limit: int = 2) -> list:
    items = [item for item in io.read_items(io.DATASET_PATH) if item.category in SCOPE]
    assert len(items) >= limit, "the dataset must have scoped items"
    return items[:limit]


def _filled_sheet(items: list, *, disagree_first: bool = False) -> dict:
    sheet = stability.emit(items, round_id="t-round")
    by_id = {item.id: item for item in items}
    for n, entry in enumerate(sheet["items"]):
        item = by_id[entry["id"]]
        gold = item.gold_labels[entry["question"]]
        levels = len(entry["criteria"])
        if disagree_first and n == 0:
            entry["relabel"] = (gold + 1) % levels
        else:
            entry["relabel"] = gold
    return sheet


# ---------------------------------------------------------------------------
# emit
# ---------------------------------------------------------------------------


def test_emit_blinds_the_original_labels() -> None:
    """The sheet carries the rubric and the state but never the gold level."""
    items = _scoped_items()
    sheet = stability.emit(items, round_id="t-round")
    by_id = {item.id: item for item in items}
    assert sheet["round_id"] == "t-round"
    assert sheet["cooling_off"]
    for entry in sheet["items"]:
        item = by_id[entry["id"]]
        assert entry["category"] == item.category
        question = item.questions[entry["question"]]
        assert entry["criteria"] == question["criteria"]
        assert isinstance(entry["anchors"], list), "anchors travel as a list"
        assert entry["state"] is not None
        assert entry["relabel"] is None
        assert "original" not in entry
        assert len(entry["original_sha256"]) == 64


def test_emit_covers_only_the_scoped_recipes() -> None:
    """Only ``change_risk``/``risk`` and ``effort_approach``/``effort`` are emitted."""
    items = io.read_items(io.DATASET_PATH)[:60]
    sheet = stability.emit(items, round_id="t-round")
    assert {entry["category"] for entry in sheet["items"]} <= set(SCOPE)


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


def test_ingest_writes_a_round_record(tmp_path: Path) -> None:
    """A filled sheet becomes a committed round record with computed agreement."""
    items = _scoped_items()
    sheet = _filled_sheet(items, disagree_first=True)
    round_ = stability.ingest(sheet, items, directory=tmp_path)
    assert isinstance(round_, StabilityRound)
    data = json.loads((tmp_path / "t-round.json").read_text(encoding="utf-8"))
    assert data["round_id"] == "t-round"
    assert len(data["entries"]) == len(items)
    agrees = [entry["agrees"] for entry in data["entries"]]
    assert agrees[0] is False, "the forced disagreement must be recorded"
    assert all(agrees[1:]), "matching re-labels must agree"


def test_ingest_rejects_an_unknown_item(tmp_path: Path) -> None:
    items = _scoped_items()
    sheet = _filled_sheet(items)
    sheet["items"][0]["id"] = "nope_999"
    with pytest.raises(StabilityError):
        stability.ingest(sheet, items, directory=tmp_path)
    assert not list(tmp_path.glob("*.json")), "nothing may be written on refusal"


def test_ingest_rejects_a_duplicate_item(tmp_path: Path) -> None:
    items = _scoped_items()
    sheet = _filled_sheet(items)
    sheet["items"].append(dict(sheet["items"][0]))
    with pytest.raises(StabilityError):
        stability.ingest(sheet, items, directory=tmp_path)
    assert not list(tmp_path.glob("*.json"))


def test_ingest_rejects_an_unfilled_relabel(tmp_path: Path) -> None:
    items = _scoped_items()
    sheet = _filled_sheet(items)
    sheet["items"][0]["relabel"] = None
    with pytest.raises(StabilityError):
        stability.ingest(sheet, items, directory=tmp_path)
    assert not list(tmp_path.glob("*.json"))


def test_ingest_rejects_a_changed_gold(tmp_path: Path) -> None:
    """A gold change between emit and ingest is an error, not a silent update."""
    items = _scoped_items()
    sheet = _filled_sheet(items)
    changed = [
        item.model_copy(
            update={
                "gold_labels": {
                    **item.gold_labels,
                    "risk" if "risk" in item.gold_labels else "effort": 3,
                }
            }
        )
        for item in items
    ]
    with pytest.raises(StabilityError):
        stability.ingest(sheet, changed, directory=tmp_path)
    assert not list(tmp_path.glob("*.json"))


# ---------------------------------------------------------------------------
# compute / load / render
# ---------------------------------------------------------------------------


def test_compute_reports_agreement_by_recipe_and_label(tmp_path: Path) -> None:
    items = _scoped_items()
    round_ = stability.ingest(
        _filled_sheet(items, disagree_first=True), items, directory=tmp_path
    )
    results = stability.compute([round_])
    coverage = {entry.category for entry in round_.entries}
    for category in coverage:
        result = results[category]
        assert 0.0 <= result.agreement <= 1.0
        assert result.rater_count == 1
    disagreeing = {entry.id for entry in round_.entries if not entry.agrees}
    assert disagreeing <= set(results[next(iter(coverage))].unstable)


def test_load_rounds_round_trips(tmp_path: Path) -> None:
    items = _scoped_items()
    written = stability.ingest(_filled_sheet(items), items, directory=tmp_path)
    loaded = stability.load_rounds(tmp_path)
    assert loaded == [written]


def test_render_mentions_single_rater(tmp_path: Path) -> None:
    items = _scoped_items()
    round_ = stability.ingest(_filled_sheet(items), items, directory=tmp_path)
    text = stability.render(stability.compute([round_]))
    lowered = text.lower()
    assert "single" in lowered
    assert "rater" in lowered


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def test_main_emit_writes_a_sheet_without_touching_the_repo(tmp_path: Path) -> None:
    out = tmp_path / "sheet.json"
    code = stability.main(
        ["--emit", "--out", str(out), "--dataset", str(io.DATASET_PATH)]
    )
    assert code == 0
    sheet = json.loads(out.read_text(encoding="utf-8"))
    assert sheet["items"], "the sheet must contain the scoped items"


def test_main_report_without_rounds_is_a_clean_noop(tmp_path: Path) -> None:
    code = stability.main(["--report", "--rounds-dir", str(tmp_path)])
    assert code == 0
    assert not list(tmp_path.glob("*.json"))
