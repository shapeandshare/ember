"""Dataset tooling: the generated card, the provenance check, and difficulty tiers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals.dataset import card, check, hashes, io, register, splitting, tiers
from evals.dataset.records.item import Item
from evals.dataset.records.split import Split

HASH64 = "d" * 64
QUESTIONS = {
    "owner": {
        "type": "choice",
        "instructions": "Which part of the system should handle this?",
        "criteria": {"api": "HTTP", "storage": "DB"},
    }
}


def item(item_id: str, *, split: str = "dev", **extra: object) -> Item:
    payload: dict[str, object] = {
        "id": item_id,
        "category": "routing",
        "split": split,
        "state": f"error in {item_id}",
        "questions": QUESTIONS,
        "gold_labels": {"owner": "api"},
        "rationale": "constructed",
        "source": {"kind": "authored", "dataset_version": HASH64},
        **extra,
    }
    return Item(**payload)  # type: ignore[arg-type]


# ###########################################################################
# card
# ###########################################################################


def test_card_has_every_contracted_field() -> None:
    items = [item("a"), item("b", split="test", tier="easy")]
    built = card.build(items, [], [], register_sha256="e" * 64)
    recipe = built["recipes"]["routing"]
    for key in (
        "items",
        "per_label_per_split",
        "kind_shares",
        "source_shares",
        "easy_items",
        "external_sources",
        "label_stability",
        "inter_source_agreement",
        "rater_count",
        "second_review_pending",
        "acted_differs_share",
        "recipe_sha256",
        "gaps",
        "exemptions",
    ):
        assert key in recipe, key
    assert recipe["label_stability"] is None
    assert recipe["inter_source_agreement"] is None
    assert recipe["acted_differs_share"] is None
    assert recipe["rater_count"] == 1
    assert recipe["easy_items"] == 1
    assert recipe["kind_shares"]["untagged"] == 2
    assert recipe["per_label_per_split"]["owner"]['"api"'] == {"dev": 1, "test": 1}
    for key in ("dataset_content_sha256", "register_sha256", "generated_from"):
        assert key in built, key


def test_card_markdown_is_deterministic() -> None:
    items = [item("a")]
    built = card.build(items, [], [], register_sha256="e" * 64)
    assert card.render_markdown(built) == card.render_markdown(built)
    assert "routing" in card.render_markdown(built)


def test_committed_card_is_fresh() -> None:
    assert card.main(["--check"]) == 0


# ###########################################################################
# check
# ###########################################################################


def test_check_passes_the_committed_dataset() -> None:
    assert check.main([]) == 0


def test_check_names_unresolvable_sources_and_missing_lock_entries() -> None:
    missing_row = item(
        "i1", source={"kind": "imported", "register_row": "nope", "record_id": "1"}
    )
    orphan = item(
        "p1",
        source={"kind": "perturbed", "parent_id": "ghost", "perturbation": "format"},
    )
    lock = {"i1": Split.dev}
    problems = check.run([missing_row, orphan], lock, [], [])
    joined = "\n".join(problems)
    for needle in ("i1", "nope", "p1", "ghost", "splits.lock"):
        assert needle in joined, needle


def test_source_rejects_a_malformed_commit_before_check_runs() -> None:
    with pytest.raises(ValueError, match="40-hex"):
        item(
            "m1",
            source={
                "kind": "mined",
                "artefact": "vault/x.md",
                "commit": "f" * 39 + "g",
            },
        )


def test_check_validates_example_secrets() -> None:
    from evals.dataset.records.example_secret import ExampleSecret

    with pytest.raises(ValueError, match="unique"):
        register.validate_example_secrets(
            [
                ExampleSecret(
                    value="X", vendor="v", url="https://a", read_on="2026-10-10"
                ),
                ExampleSecret(
                    value="X", vendor="v", url="https://b", read_on="2026-10-10"
                ),
            ]
        )
    with pytest.raises(Exception):  # noqa: B017, PT011 - any validation error will do
        ExampleSecret(value="X", vendor="v", url="", read_on="2026-10-10")


# ###########################################################################
# tiers
# ###########################################################################


def _row(run_id: str, recipes: dict[str, str]) -> dict[str, object]:
    return {"run_id": run_id, "recipes": {c: {"run_id": r} for c, r in recipes.items()}}


def test_easy_ids_require_every_row_to_be_fully_correct() -> None:
    rows = [_row("r1", {"routing": "r1"}), _row("r2", {"routing": "r2"})]
    traces = {
        "r1": [
            {"id": "a", "category": "routing", "correct": True},
            {"id": "b", "category": "routing", "correct": True},
        ],
        "r2": [
            {"id": "a", "category": "routing", "correct": True},
            {"id": "b", "category": "routing", "correct": False},
        ],
    }
    assert tiers.easy_ids(rows, traces) == {"a"}


def test_easy_ids_ignore_rows_lacking_the_recipe() -> None:
    rows = [_row("r1", {"routing": "r1"}), _row("r2", {"change_risk": "r2"})]
    traces = {
        "r1": [{"id": "a", "category": "routing", "correct": True}],
        "r2": [{"id": "k", "category": "change_risk", "correct": False}],
    }
    assert tiers.easy_ids(rows, traces) == {"a"}


def test_apply_tags_easy_items_without_changing_the_content_hash() -> None:
    items = [item("a"), item("b", tier="easy")]
    before = hashes.dataset_content_sha256(items)
    tagged = tiers.apply(items, {"a"})
    assert [i.tier for i in tagged] == ["easy", None]
    assert hashes.dataset_content_sha256(tagged) == before


def test_tier_main_fails_without_rows_on_the_current_version(tmp_path: Path) -> None:
    dataset = tmp_path / "d.jsonl"
    io.write_items(dataset, [item("a")])
    (tmp_path / "benchmark").mkdir()
    assert (
        tiers.main(["--from", str(tmp_path / "benchmark"), "--dataset", str(dataset)])
        == 1
    )


def test_split_lock_covers_the_committed_dataset() -> None:
    items = io.read_items(io.DATASET_PATH)
    lock = splitting.read_lock(splitting.LOCK_PATH)
    assert {i.id: i.split for i in items} == lock
    assert json.loads(splitting.LOCK_PATH.read_text(encoding="utf-8"))


# ###########################################################################
# Protocol and rubric versions (FR-046)
# ###########################################################################


def test_protocol_rules_and_scales_name_a_recorded_version() -> None:
    from evals.dataset import protocol, scales

    versions = protocol.read_versions()
    current = hashes.dataset_content_sha256(io.read_items(io.DATASET_PATH))
    assert current in versions
    assert protocol.RULES
    for rule in protocol.RULES:
        assert rule.since in versions, rule.text[:40]
    for scale in scales.SCALES.values():
        assert scale.since in versions, scale.question


def test_record_version_is_append_only_and_idempotent(tmp_path: Path) -> None:
    from evals.dataset import protocol

    path = tmp_path / "versions.lock"
    assert protocol.record_version("a" * 64, path=path, recorded_on="2026-10-10")
    assert not protocol.record_version("a" * 64, path=path, recorded_on="2026-10-11")
    assert protocol.record_version("b" * 64, path=path, recorded_on="2026-10-11")
    assert protocol.read_versions(path) == ["a" * 64, "b" * 64]


def test_check_fails_on_an_unrecorded_protocol_or_dataset_version() -> None:
    items = [item("a"), item("b", split="test")]
    lock = {"a": Split.dev, "b": Split.test}
    problems = check.run(items, lock, [], [], versions=["0" * 64])
    joined = "\n".join(problems)
    assert "not a recorded dataset version" in joined
    assert "protocol rule" in joined
    assert "scale change_risk/risk" in joined
    current = hashes.dataset_content_sha256(items)
    assert current[:12] in joined
    assert "run `ember eval dataset card`" in joined


def test_card_lists_protocol_rules_with_their_versions() -> None:
    from evals.dataset import protocol

    built = card.build([item("a")], [], [], register_sha256="e" * 64)
    assert [r["since"] for r in built["protocol"]] == [r.since for r in protocol.RULES]
    assert all(r["text"] for r in built["protocol"])
    assert built["recipes"]["routing"]["rubric_since"] == {}
    assert "since" in card.render_markdown(built)


def test_card_reports_the_acted_differs_share_of_captured_items() -> None:
    captured = {
        "kind": "captured",
        "session_id": "ses_1",
        "redaction_sha256": "f" * 64,
    }
    items = [
        item("c1", source=captured, acted={"owner": "storage"}, acted_differs=True),
        item("c2", source=captured, acted={"owner": "api"}, acted_differs=False),
        item("a1"),
    ]
    built = card.build(items, [], [], register_sha256="e" * 64)
    assert built["recipes"]["routing"]["acted_differs_share"] == 0.5
    assert (
        card.build([item("a1")], [], [], register_sha256="e" * 64)["recipes"][
            "routing"
        ]["acted_differs_share"]
        is None
    )


def test_card_publishes_stability_and_the_single_rater_rule() -> None:
    """The card carries label stability and names why imports are absent."""
    from evals.dataset.records.stability_result import StabilityResult

    result = StabilityResult(agreement=0.9, by_label={"0": 1.0}, unstable=["r1"])
    built = card.build(
        [item("a1")],
        [],
        [],
        register_sha256="e" * 64,
        stability={"routing": result},
    )
    routing = built["recipes"]["routing"]
    assert routing["label_stability"]["agreement"] == 0.9
    assert routing["inter_source_agreement"] is None
    markdown = card.render_markdown(built)
    assert "single-rater human" in markdown
    assert "blinded LLM panel" in markdown
    assert "none yet (no imports)" in markdown
