"""The docs watcher keeps a running ``make site-serve`` preview current."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_site_docs.py"


def _load_build_site_docs() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_site_docs", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


docs = _load_build_site_docs()


class _PollsExhaustedError(Exception):
    """Ends the otherwise endless watch loop once the scripted polls run out."""


def _idle() -> None:
    """A poll with no edit before it."""


def _touch(path: Path) -> Callable[[], None]:
    """An edit that moves ``path``'s modification time a second forward."""

    def edit() -> None:
        mtime = path.stat().st_mtime_ns + 1_000_000_000
        os.utime(path, ns=(mtime, mtime))

    return edit


def _watch(
    monkeypatch: pytest.MonkeyPatch,
    paths: list[Path],
    polls: list[Callable[[], None]],
    rebuild: Callable[[], int] = lambda: 0,
) -> int:
    """Run ``watch()`` over ``paths``, making one edit before each poll.

    Returns how many rebuilds it started.
    """
    rebuilds = 0

    def counted_rebuild() -> int:
        nonlocal rebuilds
        rebuilds += 1
        return rebuild()

    edits = iter(polls)

    def sleep(_interval: float) -> None:
        edit = next(edits, None)
        if edit is None:
            raise _PollsExhaustedError
        edit()

    monkeypatch.setattr(docs, "_watched", lambda: paths)
    monkeypatch.setattr(docs, "main", counted_rebuild)
    monkeypatch.setattr(docs.time, "sleep", sleep)
    with pytest.raises(_PollsExhaustedError):
        docs.watch()
    return rebuilds


def test_watch_rebuilds_once_after_a_source_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "README.md"
    source.write_text("before", encoding="utf-8")
    assert _watch(monkeypatch, [source], [_touch(source), _idle]) == 1


def test_watch_does_not_rebuild_while_nothing_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "README.md"
    source.write_text("unchanged", encoding="utf-8")
    assert _watch(monkeypatch, [source], [_idle, _idle]) == 0


def test_watch_rebuilds_after_a_source_is_deleted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "SECURITY.md"
    source.write_text("soon gone", encoding="utf-8")
    assert _watch(monkeypatch, [source], [source.unlink, _idle]) == 1


def test_watch_keeps_running_after_a_failed_rebuild(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = tmp_path / "docs.json"
    manifest.write_text("[]", encoding="utf-8")

    def broken_rebuild() -> int:
        raise ValueError("Expecting value: line 1 column 1 (char 0)")

    polls = [_touch(manifest), _touch(manifest)]
    assert _watch(monkeypatch, [manifest], polls, rebuild=broken_rebuild) == 2
    assert "error: Expecting value" in capsys.readouterr().err


def test_watched_covers_the_manifest_its_documents_and_the_assets() -> None:
    manifest = docs.SITE / "_data" / "docs.json"
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    sources = {docs.REPO / entry["source"] for entry in entries}
    assets = {docs.REPO / relative for relative in docs.ASSETS}
    assert set(docs._watched()) == {manifest, *sources, *assets}
