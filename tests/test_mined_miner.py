"""Tests for the mined-vault primitives and miner (specs/007)."""

from __future__ import annotations

from pathlib import Path

import pytest
from evals.dataset.mined.candidate_note import CandidateNote
from evals.dataset.mined.exclusion_reason import ExclusionReason
from evals.dataset.mined.exclusions import classify
from evals.dataset.mined.frontmatter import NoteFrontmatter, body_of, parse
from evals.dataset.mined.selection import select
from evals.dataset.mined.snapshot import VaultSnapshot, VaultSnapshotError
from evals.dataset.mined.vocabulary import TagVocabulary

from tests.fixture_vault import build_fixture_vault, commit_change

SNAPSHOT_NOTE = "Decisions/Rust-GDScript Split Architecture.md"


def test_snapshot_reads_the_commit_never_the_working_tree(tmp_path: Path) -> None:
    vault = build_fixture_vault(tmp_path)
    snapshot = VaultSnapshot(vault.root, vault.commit)
    original = snapshot.read(SNAPSHOT_NOTE)
    assert "Rust-GDScript Split Architecture" in original
    (vault.vault / SNAPSHOT_NOTE).write_text("tampered", encoding="utf-8")
    assert snapshot.read(SNAPSHOT_NOTE) == original


def test_snapshot_tree_digest_is_stable_and_commit_bound(tmp_path: Path) -> None:
    vault = build_fixture_vault(tmp_path)
    first = VaultSnapshot(vault.root, vault.commit).tree_digest()
    second = VaultSnapshot(vault.root, vault.commit).tree_digest()
    assert first == second
    moved = commit_change(vault.root, "docs/vault/index.md", "different\n")
    assert VaultSnapshot(vault.root, moved).tree_digest() != first


def test_snapshot_refuses_a_missing_commit(tmp_path: Path) -> None:
    vault = build_fixture_vault(tmp_path)
    snapshot = VaultSnapshot(vault.root, "0" * 40)
    with pytest.raises(VaultSnapshotError, match="0" * 40):
        snapshot.require()


def test_snapshot_lists_every_vault_file_sorted(tmp_path: Path) -> None:
    vault = build_fixture_vault(tmp_path)
    files = list(VaultSnapshot(vault.root, vault.commit).files())
    paths = [entry.path for entry in files]
    assert paths == sorted(paths)
    assert "_meta/tags.md" in paths
    assert all(not path.startswith("docs/") for path in paths)


def test_frontmatter_parses_and_body_strips_the_header(tmp_path: Path) -> None:
    vault = build_fixture_vault(tmp_path)
    text = (vault.vault / SNAPSHOT_NOTE).read_text(encoding="utf-8")
    meta = parse(text)
    assert isinstance(meta, NoteFrontmatter)
    assert meta.type == "decision"
    assert "type/decision" in meta.tags
    assert "# Rust-GDScript Split Architecture" in body_of(text)


def test_frontmatter_refuses_a_headerless_note() -> None:
    with pytest.raises(ValueError, match="frontmatter"):
        parse("no header here")


def test_vocabulary_parses_axes_values_and_descriptions(tmp_path: Path) -> None:
    vault = build_fixture_vault(tmp_path)
    snapshot = VaultSnapshot(vault.root, vault.commit)
    vocabulary = TagVocabulary.from_tags_md(snapshot.read("_meta/tags.md"))
    assert vocabulary.contains("type/decision")
    assert not vocabulary.contains("type/nope")
    assert not vocabulary.contains("status/in-progress")
    assert vocabulary.values_for("type") == sorted(
        [
            "type/decision",
            "type/discovery",
            "type/moc",
            "type/reference",
            "type/session-log",
            "type/spec",
        ]
    )
    block = vocabulary.as_state_block()
    assert "`type/decision`" in block
    assert "Architectural" in block


def _note_from_entry(entry) -> CandidateNote:  # type: ignore[no-untyped-def]
    meta = parse(entry.text)
    return CandidateNote(
        artefact=entry.path,
        title=meta.title,
        type=meta.type,
        tags=tuple(meta.tags),
        body=body_of(entry.text),
    )


def _fixture_snapshot(tmp_path: Path):  # type: ignore[no-untyped-def]
    vault = build_fixture_vault(tmp_path)
    snapshot = VaultSnapshot(vault.root, vault.commit)
    vocabulary = TagVocabulary.from_tags_md(snapshot.read("_meta/tags.md"))
    return snapshot, vocabulary


def _fixture_candidates(tmp_path: Path) -> list[CandidateNote]:
    snapshot, vocabulary = _fixture_snapshot(tmp_path)
    return [
        _note_from_entry(entry)
        for entry in snapshot.files()
        if not entry.path.startswith("_meta/")
        and classify(_note_from_entry(entry), vocabulary) is None
    ]


def test_exclusions_record_each_reason(tmp_path: Path) -> None:
    snapshot, vocabulary = _fixture_snapshot(tmp_path)
    reasons = {}
    for entry in snapshot.files():
        if entry.path.startswith("_meta/"):
            continue
        record = classify(_note_from_entry(entry), vocabulary)
        if record is not None:
            reasons[record.artefact] = record.reason
    assert reasons["Decisions/Drifted Tags.md"] is ExclusionReason.drift
    assert reasons["Audio.md"] is ExclusionReason.non_content
    assert reasons["index.md"] is ExclusionReason.non_content
    assert reasons["README.md"] is ExclusionReason.non_content
    assert (
        reasons["Specs/047 Car Radio/047 Car Radio.md"] is ExclusionReason.out_of_scope
    )
    assert reasons["Discoveries/A Secret Was Left Here.md"] is ExclusionReason.secret
    assert reasons["Narrative/Empty Tags.md"] is ExclusionReason.tag_set_bounds
    for kept in (
        "Decisions/Rust-GDScript Split Architecture.md",
        "Discoveries/Generation Pipeline Order.md",
        "Reference/Glossary.md",
        "Sessions/Spec 080 Planning Session.md",
    ):
        assert kept not in reasons, kept


def test_selection_is_seeded_and_spreads_types() -> None:
    candidates = [
        CandidateNote(
            artefact=f"Notes/{index:02d}.md",
            title=f"Note {index}",
            type=note_type,
            tags=(f"type/{note_type}",),
            body="body",
        )
        for index, note_type in enumerate(
            ["decision", "discovery", "reference", "session-log"] * 4
        )
    ]
    first = select(candidates, count=6, seed=7)
    again = select(candidates, count=6, seed=7)
    assert [note.artefact for note in first] == [note.artefact for note in again]
    assert len({note.type for note in first}) == 4
    other = select(candidates, count=6, seed=99)
    assert [note.artefact for note in other] != [note.artefact for note in first]


def test_selection_returns_everything_when_fewer_than_the_count(
    tmp_path: Path,
) -> None:
    candidates = _fixture_candidates(tmp_path)
    picked = select(candidates, count=65)
    assert len(picked) == len(candidates) >= 4
