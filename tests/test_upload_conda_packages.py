"""Unit tests for scripts/upload_conda_packages.py (network-free)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "upload_conda_packages.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("upload_conda_packages", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


upload = _load()


def test_discover_packages_finds_conda_files_recursively(tmp_path: Path) -> None:
    (tmp_path / "linux").mkdir()
    (tmp_path / "linux" / "x.conda").write_bytes(b"")
    (tmp_path / "y.conda").write_bytes(b"")
    (tmp_path / "z.tar.bz2").write_bytes(b"")

    names = [path.name for path in upload.discover_packages(tmp_path)]

    assert names == ["x.conda", "y.conda"]


def test_upload_argv_sets_user_and_skips_existing() -> None:
    argv = upload.upload_argv("joshburt", [Path("dist/x.conda")])

    assert argv[:5] == ["anaconda", "upload", "--user", "joshburt", "--skip-existing"]
    assert argv[-1] == "dist/x.conda"


def test_require_token_rejects_a_missing_token() -> None:
    with pytest.raises(ValueError, match="ANACONDA_API_TOKEN"):
        upload.require_token({})


def test_require_token_rejects_a_blank_token() -> None:
    with pytest.raises(ValueError, match="ANACONDA_API_TOKEN"):
        upload.require_token({"ANACONDA_API_TOKEN": "   "})


def test_publish_uploads_every_package(tmp_path: Path) -> None:
    (tmp_path / "x.conda").write_bytes(b"")
    seen: dict[str, list[str]] = {}

    def fake_run(argv: list[str]) -> int:
        seen["argv"] = argv
        return 0

    code = upload.publish(
        tmp_path, "joshburt", env={"ANACONDA_API_TOKEN": "t"}, run=fake_run
    )

    assert code == 0
    assert seen["argv"][-1].endswith("x.conda")


def test_publish_refuses_without_a_token(tmp_path: Path) -> None:
    (tmp_path / "x.conda").write_bytes(b"")

    def fake_run(argv: list[str]) -> int:  # pragma: no cover - must not be called
        raise AssertionError("must not upload without a token")

    with pytest.raises(ValueError, match="ANACONDA_API_TOKEN"):
        upload.publish(tmp_path, "joshburt", env={}, run=fake_run)


def test_publish_errors_when_no_packages(tmp_path: Path) -> None:
    def fake_run(argv: list[str]) -> int:  # pragma: no cover - must not be called
        raise AssertionError("must not upload with nothing to upload")

    code = upload.publish(
        tmp_path, "joshburt", env={"ANACONDA_API_TOKEN": "t"}, run=fake_run
    )

    assert code == 1


def test_publish_reports_a_failed_upload(tmp_path: Path) -> None:
    (tmp_path / "x.conda").write_bytes(b"")

    def fake_run(argv: list[str]) -> int:
        return 3

    code = upload.publish(
        tmp_path, "joshburt", env={"ANACONDA_API_TOKEN": "t"}, run=fake_run
    )

    assert code == 1
