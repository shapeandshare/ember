"""Unit tests for Codex CLI project-trust lookup (mirrors codex-rs trust lookup)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ember.codex.codex_trust import CodexTrust, trust_level


@pytest.fixture
def codex_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    return home


def _trust(codex_home: Path, entries: dict[str, str | None]) -> None:
    lines: list[str] = []
    for key, level in entries.items():
        lines.append(f"[projects.{json.dumps(key)}]")
        if level is not None:
            lines.append(f"trust_level = {json.dumps(level)}")
    (codex_home / "config.toml").write_text("\n".join(lines) + "\n")


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    sub = repo / "pkg"
    sub.mkdir()
    return repo, sub


def test_trust_level_is_none_without_a_global_config(
    tmp_path: Path, codex_home: Path
) -> None:
    assert trust_level(tmp_path) is None


def test_trust_level_reads_a_trusted_project(tmp_path: Path, codex_home: Path) -> None:
    _trust(codex_home, {str(tmp_path.resolve()): "trusted"})
    assert trust_level(tmp_path) is CodexTrust.TRUSTED


def test_trust_level_reads_an_explicitly_untrusted_project(
    tmp_path: Path, codex_home: Path
) -> None:
    _trust(codex_home, {str(tmp_path.resolve()): "untrusted"})
    assert trust_level(tmp_path) is CodexTrust.UNTRUSTED


def test_trust_level_matches_the_path_as_spelled(
    tmp_path: Path, codex_home: Path
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real)
    _trust(codex_home, {str(alias): "trusted"})
    assert trust_level(alias) is CodexTrust.TRUSTED


def test_trust_level_matches_the_canonical_path_of_an_alias(
    tmp_path: Path, codex_home: Path
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real)
    _trust(codex_home, {str(real.resolve()): "trusted"})
    assert trust_level(alias) is CodexTrust.TRUSTED


def test_trusting_the_repository_root_covers_a_subdirectory(
    tmp_path: Path, codex_home: Path
) -> None:
    repo, sub = _repo(tmp_path)
    _trust(codex_home, {str(repo.resolve()): "trusted"})
    assert trust_level(sub) is CodexTrust.TRUSTED


def test_a_cwd_entry_without_a_level_shadows_a_trusted_repository_root(
    tmp_path: Path, codex_home: Path
) -> None:
    repo, sub = _repo(tmp_path)
    _trust(codex_home, {str(sub.resolve()): None, str(repo.resolve()): "trusted"})
    assert trust_level(sub) is None


def test_trusting_the_main_checkout_covers_a_linked_worktree(
    tmp_path: Path, codex_home: Path
) -> None:
    main = tmp_path / "main"
    admin = main / ".git" / "worktrees" / "wt"
    admin.mkdir(parents=True)
    (admin / "commondir").write_text("../..\n")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {admin}\n")
    _trust(codex_home, {str(main.resolve()): "trusted"})
    assert trust_level(worktree) is CodexTrust.TRUSTED


def test_trusting_a_parent_directory_does_not_cover_a_non_repo_child(
    tmp_path: Path, codex_home: Path
) -> None:
    child = tmp_path / "child"
    child.mkdir()
    _trust(codex_home, {str(tmp_path.resolve()): "trusted"})
    assert trust_level(child) is None


def test_an_unknown_trust_level_counts_as_undecided(
    tmp_path: Path, codex_home: Path
) -> None:
    _trust(codex_home, {str(tmp_path.resolve()): "maybe"})
    assert trust_level(tmp_path) is None


def test_a_malformed_global_config_counts_as_undecided(
    tmp_path: Path, codex_home: Path
) -> None:
    (codex_home / "config.toml").write_text("this = is [ not toml")
    assert trust_level(tmp_path) is None
