"""Decision logic for scripts/freeze_conda_lock.py — no conda-lock or network needed."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "freeze_conda_lock.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("freeze_conda_lock", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


freeze = _load()


def _fake_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(freeze, "ROOT", tmp_path)
    (tmp_path / "conda").mkdir()
    (tmp_path / freeze.LOCK).write_text("version: 1\n", encoding="utf-8")
    for platform in freeze.PLATFORMS:
        (tmp_path / freeze._explicit_lock(platform)).write_text(
            "# explicit\n", encoding="utf-8"
        )


def test_lock_argv_regenerates_the_committed_lock() -> None:
    argv = freeze._lock_argv(freeze.LOCK, check=False)
    assert argv == [
        "conda-lock",
        "-f",
        "conda/lock-environment.yml",
        "-p",
        "osx-arm64",
        "-p",
        "linux-64",
        "--lockfile",
        "conda/ember-deps.conda-lock.yml",
    ]


def test_lock_argv_check_mode_inserts_check_input_hash() -> None:
    argv = freeze._lock_argv(freeze.CHECK_LOCK, check=True)
    assert argv[:2] == ["conda-lock", "--check-input-hash"]
    assert argv[-1] == str(freeze.CHECK_LOCK)


def test_verify_lock_reports_missing_platforms(tmp_path: Path) -> None:
    lock = tmp_path / "lock.yml"
    lock.write_text(yaml.safe_dump({"package": [{"platform": "osx-arm64"}]}))
    assert freeze._verify_lock(lock) == ["linux-64"]


def test_verify_lock_accepts_both_platforms(tmp_path: Path) -> None:
    lock = tmp_path / "lock.yml"
    lock.write_text(
        yaml.safe_dump(
            {"package": [{"platform": "osx-arm64"}, {"platform": "linux-64"}]}
        )
    )
    assert freeze._verify_lock(lock) == []


def test_check_reports_in_sync_on_exit_four(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _fake_root(tmp_path, monkeypatch)
    monkeypatch.setattr(freeze, "_run", lambda argv: freeze.IN_SYNC_CODE)
    assert freeze._check() == 0
    assert "in sync" in capsys.readouterr().out
    assert not (tmp_path / freeze.CHECK_LOCK).exists()


def test_check_reports_stale_on_exit_zero(tmp_path: Path, monkeypatch, capsys) -> None:
    _fake_root(tmp_path, monkeypatch)

    def fake_run(argv: list[str]) -> int:
        (tmp_path / freeze.CHECK_LOCK).write_text("# re-locked\n")
        return 0

    monkeypatch.setattr(freeze, "_run", fake_run)
    assert freeze._check() == 1
    assert "make conda-lock" in capsys.readouterr().err


def test_check_reports_in_sync_when_left_unchanged(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _fake_root(tmp_path, monkeypatch)
    monkeypatch.setattr(freeze, "_run", lambda argv: 0)
    assert freeze._check() == 0
    assert "in sync" in capsys.readouterr().out


def test_check_reports_unexpected_exit(tmp_path: Path, monkeypatch, capsys) -> None:
    _fake_root(tmp_path, monkeypatch)
    monkeypatch.setattr(freeze, "_run", lambda argv: 2)
    assert freeze._check() == 1
    assert "exit 2" in capsys.readouterr().err


def test_check_errors_when_the_lock_is_missing(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(freeze, "ROOT", tmp_path)
    assert freeze._check() == 1
    assert "make conda-lock" in capsys.readouterr().err


def test_regenerate_reports_platform_gaps(tmp_path: Path, monkeypatch, capsys) -> None:
    _fake_root(tmp_path, monkeypatch)
    (tmp_path / freeze.LOCK).write_text(
        yaml.safe_dump({"package": [{"platform": "osx-arm64"}]})
    )
    monkeypatch.setattr(freeze, "_run", lambda argv: 0)
    assert freeze._regenerate() == 1
    assert "linux-64" in capsys.readouterr().err


def test_render_argv_targets_an_explicit_platform_lock() -> None:
    assert freeze._render_argv("linux-64") == [
        "conda-lock",
        "render",
        "--kind",
        "explicit",
        "-p",
        "linux-64",
        "conda/ember-deps.conda-lock.yml",
    ]


def test_regenerate_renders_and_verifies_explicit_locks(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _fake_root(tmp_path, monkeypatch)
    (tmp_path / freeze.LOCK).write_text(
        yaml.safe_dump(
            {"package": [{"platform": "osx-arm64"}, {"platform": "linux-64"}]}
        )
    )
    rendered = []

    def fake_run(argv: list[str]) -> int:
        if argv[:2] == ["conda-lock", "render"]:
            platform = argv[argv.index("-p") + 1]
            rendered.append(platform)
            (tmp_path / f"conda-{platform}.lock").write_text("# explicit\n")
        return 0

    monkeypatch.setattr(freeze, "_run", fake_run)
    assert freeze._regenerate() == 0
    assert sorted(rendered) == ["linux-64", "osx-arm64"]
    assert "explicit locks" in capsys.readouterr().out


def test_regenerate_reports_missing_explicit_lock(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _fake_root(tmp_path, monkeypatch)
    (tmp_path / freeze.LOCK).write_text(
        yaml.safe_dump(
            {"package": [{"platform": "osx-arm64"}, {"platform": "linux-64"}]}
        )
    )
    monkeypatch.setattr(freeze, "_run", lambda argv: 0)
    (tmp_path / "conda-linux-64.lock").unlink()
    assert freeze._regenerate() == 1
    assert "explicit locks missing" in capsys.readouterr().err


def test_check_reports_missing_explicit_lock(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _fake_root(tmp_path, monkeypatch)
    monkeypatch.setattr(freeze, "_run", lambda argv: freeze.IN_SYNC_CODE)
    (tmp_path / "conda-osx-arm64.lock").unlink()
    assert freeze._check() == 1
    assert "explicit locks missing" in capsys.readouterr().err
