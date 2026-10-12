"""Unit tests for the operator CLI's .env loading (environment wins)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def test_load_sets_unset_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A .env value fills a variable that is not set in the environment."""
    monkeypatch.delenv("TS_OAUTH_CLIENT_ID", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("TS_OAUTH_CLIENT_ID=from-file\n")

    from ember_aws import dotenv

    dotenv.load(env_file)

    assert os.environ["TS_OAUTH_CLIENT_ID"] == "from-file"


def test_load_never_overrides_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exported value wins over the .env file (GNU make precedent aside)."""
    monkeypatch.setenv("TS_OAUTH_CLIENT_ID", "real-value")
    env_file = tmp_path / ".env"
    env_file.write_text("TS_OAUTH_CLIENT_ID=from-file\n")

    from ember_aws import dotenv

    dotenv.load(env_file)

    assert os.environ["TS_OAUTH_CLIENT_ID"] == "real-value"


def test_load_skips_blank_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A blank assignment (the .env.example default) sets nothing."""
    monkeypatch.delenv("TS_OAUTH_CLIENT_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nexport TS_OAUTH_CLIENT_SECRET=\n")

    from ember_aws import dotenv

    dotenv.load(env_file)

    assert "TS_OAUTH_CLIENT_SECRET" not in os.environ


def test_load_missing_file_is_not_an_error(tmp_path: Path) -> None:
    """A missing .env is normal; loading does not raise."""
    from ember_aws import dotenv

    dotenv.load(tmp_path / "absent.env")


def test_main_loads_dotenv_before_building() -> None:
    """main() loads .env, then dispatches to build()."""
    from ember_aws import __main__ as main_mod

    with (
        patch.object(main_mod.dotenv, "load") as mock_load,
        patch.object(main_mod, "build", return_value=0) as mock_build,
        patch.object(sys, "argv", ["ember_aws", "preflight"]),
    ):
        code = main_mod.main()

    assert code == 0
    mock_load.assert_called_once_with()
    mock_build.assert_called_once_with(["preflight"])


def test_build_does_not_load_dotenv() -> None:
    """build() itself stays pure: no .env side effect when parsing."""
    from ember_aws.__main__ import build

    with patch("ember_aws.__main__.dotenv.load") as mock_load:
        code = build([])

    assert code == 1  # no subcommand: help
    mock_load.assert_not_called()
