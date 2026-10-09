"""Unit tests for git checkout-root discovery (reads ``.git``, never runs git)."""

from __future__ import annotations

from pathlib import Path

from ember.cfg.repo_root import checkout_root, main_checkout_root


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    admin = main / ".git" / "worktrees" / "wt"
    admin.mkdir(parents=True)
    (admin / "commondir").write_text("../..\n")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {admin}\n")
    return main, worktree


def test_checkout_root_finds_the_nearest_dot_git_ancestor(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert checkout_root(nested) == tmp_path


def test_checkout_root_is_none_outside_a_checkout(tmp_path: Path) -> None:
    assert checkout_root(tmp_path) is None


def test_main_checkout_root_maps_a_linked_worktree_to_its_repository(
    tmp_path: Path,
) -> None:
    main, worktree = _linked_worktree(tmp_path)
    assert main_checkout_root(worktree) == main.resolve()


def test_main_checkout_root_keeps_a_plain_checkout(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert main_checkout_root(tmp_path) == tmp_path


def test_main_checkout_root_keeps_a_submodule_checkout(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / ".git" / "modules" / "sub").mkdir(parents=True)
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n")
    assert main_checkout_root(sub) == sub


def test_main_checkout_root_is_none_outside_a_checkout(tmp_path: Path) -> None:
    assert main_checkout_root(tmp_path) is None
