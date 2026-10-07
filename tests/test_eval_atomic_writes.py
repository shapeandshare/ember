"""Unit tests for atomic writes in the eval harness (constitution §10.17)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from evals import export


def test_write_atomic_writes_content_and_leaves_no_tmp(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "results.json"

    export.write_atomic(target, "{}\n")

    assert target.read_text(encoding="utf-8") == "{}\n"
    assert list(target.parent.glob("*.tmp")) == []


def test_write_atomic_keeps_original_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "results.json"
    target.write_text("original", encoding="utf-8")

    def boom(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        export.write_atomic(target, "new")

    assert target.read_text(encoding="utf-8") == "original"


def test_copy_atomic_copies_file(tmp_path: Path) -> None:
    source = tmp_path / "a.jsonl"
    source.write_text("line\n", encoding="utf-8")
    target = tmp_path / "out" / "b.jsonl"

    export.copy_atomic(source, target)

    assert target.read_text(encoding="utf-8") == "line\n"
    assert list(target.parent.glob("*.tmp")) == []
