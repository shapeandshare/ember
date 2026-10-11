"""Dataset io and hashes: the legacy source shim, round-trips, and the
scoring projection behind the content, per-recipe, and file hashes.

Shares the record helpers of ``tests/test_dataset_tooling.py``.
"""

from __future__ import annotations

import pytest

from tests.test_dataset_tooling import HASH64, SHA40, _item, _source

# ###########################################################################
# io: read, write, and the legacy source shim
# ###########################################################################


def _write_lines(path, records: list[dict[str, object]]) -> None:  # type: ignore[no-untyped-def]
    import json

    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def test_read_items_maps_legacy_string_sources_to_authored(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from evals.dataset import io
    from evals.dataset.records.source_kind import SourceKind

    path = tmp_path / "d.jsonl"
    _write_lines(
        path,
        [
            _item(id="a", source="curated"),
            _item(id="b", source="skill_md"),
        ],
    )
    items = io.read_items(path, legacy_dataset_version=HASH64)
    assert [i.source.kind for i in items] == [SourceKind.authored, SourceKind.authored]
    assert items[0].source.dataset_version == HASH64
    assert items[0].source.note is None
    assert items[1].source.note == (
        "reproduces a worked example in ember/agent_kit/ember-advise/SKILL.md"
    )


def test_read_items_without_a_legacy_version_rejects_string_sources(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from evals.dataset import io

    path = tmp_path / "d.jsonl"
    _write_lines(path, [_item(id="a", source="curated")])
    with pytest.raises(ValueError, match="legacy"):
        io.read_items(path)


def test_write_items_round_trips_in_order_without_nulls(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    from evals.dataset import io

    path = tmp_path / "d.jsonl"
    _write_lines(path, [_item(id="b"), _item(id="a")])
    items = io.read_items(path)
    out = tmp_path / "out.jsonl"
    io.write_items(out, items)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["id"] for line in lines] == ["b", "a"]
    assert "null" not in lines[0]
    assert io.read_items(out) == items


# ###########################################################################
# hashes: the scoring projection
# ###########################################################################


def test_projection_contains_exactly_the_scored_fields() -> None:
    from evals.dataset import hashes
    from evals.dataset.records.item import Item

    item = Item(**_item())  # type: ignore[arg-type]
    assert set(hashes.projection(item)) == {
        "id",
        "category",
        "split",
        "state",
        "questions",
        "gold_labels",
    }
    with_media = Item(**_item(images=["data:image/png;base64,AAAA"]))  # type: ignore[arg-type]
    assert "images" in hashes.projection(with_media)


def test_content_hashes_ignore_annotations_and_track_scored_content() -> None:
    from evals.dataset import hashes
    from evals.dataset.records.item import Item

    base = [Item(**_item(id="a")), Item(**_item(id="b", category="routing"))]  # type: ignore[arg-type]
    annotated = [
        Item(  # type: ignore[arg-type]
            **_item(
                id="a",
                rationale="different words",
                kind="control",
                tier="easy",
                source=_source("mined", artefact="vault/x.md", commit=SHA40),
            )
        ),
        base[1],
    ]
    assert hashes.dataset_content_sha256(base) == hashes.dataset_content_sha256(
        annotated
    )
    assert hashes.recipe_sha256(base) == hashes.recipe_sha256(annotated)
    relabelled = [Item(**_item(id="a", gold_labels={"owner": "storage"})), base[1]]  # type: ignore[arg-type]
    assert hashes.dataset_content_sha256(base) != hashes.dataset_content_sha256(
        relabelled
    )
    moved = [Item(**_item(id="a", split="test")), base[1]]  # type: ignore[arg-type]
    assert hashes.recipe_sha256(base) != hashes.recipe_sha256(moved)
    assert hashes.recipe_sha256(base) == hashes.recipe_sha256(list(reversed(base)))


def test_recipe_hash_is_isolated_per_recipe_and_file_hash_is_bytes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import hashlib

    from evals.dataset import hashes
    from evals.dataset.records.item import Item

    routing = Item(**_item(id="r1"))  # type: ignore[arg-type]
    risk_a = Item(  # type: ignore[arg-type]
        **_item(
            id="k1",
            category="change_risk",
            questions={"needs_review": {"type": "noul", "instructions": "Review?"}},
            gold_labels={"needs_review": True},
        )
    )
    risk_b = Item(  # type: ignore[arg-type]
        **_item(
            id="k1",
            category="change_risk",
            state="other diff",
            questions={"needs_review": {"type": "noul", "instructions": "Review?"}},
            gold_labels={"needs_review": True},
        )
    )
    assert (
        hashes.recipe_hashes([routing, risk_a])["routing"]
        == hashes.recipe_hashes([routing, risk_b])["routing"]
    )
    assert (
        hashes.recipe_hashes([routing, risk_a])["change_risk"]
        != hashes.recipe_hashes([routing, risk_b])["change_risk"]
    )
    path = tmp_path / "f.jsonl"
    path.write_bytes(b"{}\n")
    assert hashes.dataset_sha256(path) == hashlib.sha256(b"{}\n").hexdigest()


def test_raw_and_validated_items_hash_identically_for_the_committed_dataset() -> None:
    """The harness hashes raw records; the card, CLI, and tiers hash ``Item``s.

    They must agree, or a run and the card would disagree about the version.
    """
    from evals.dataset import hashes, io

    raw = io.read_raw(io.DATASET_PATH)
    items = io.read_items(io.DATASET_PATH)
    assert hashes.dataset_content_sha256(raw) == hashes.dataset_content_sha256(items)
    assert hashes.recipe_hashes(raw) == hashes.recipe_hashes(items)


def test_raw_and_validated_items_hash_identically_with_media_and_defaults() -> None:
    from evals.dataset import hashes
    from evals.dataset.records.item import Item

    raw = [
        _item(id="a", images=["data:image/png;base64,AAAA"], media_kwargs={"fps": 1}),
        _item(id="b", videos=[["data:image/png;base64,AAAA"]]),
        _item(id="c"),
    ]
    items = [Item(**record) for record in raw]  # type: ignore[arg-type]
    assert hashes.dataset_content_sha256(raw) == hashes.dataset_content_sha256(items)
