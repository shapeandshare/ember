"""Tests for the mined-vault primitives and miner (specs/007)."""

from __future__ import annotations

from pathlib import Path

import pytest
from evals.dataset.mined.frontmatter import NoteFrontmatter, body_of, parse
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
