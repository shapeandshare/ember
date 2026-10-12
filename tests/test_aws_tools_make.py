"""Dry-run tests for the aws-tools / aws-tools-rm Makefile recipes (T056a).

These tests use ``make -n`` (dry-run / no-execute mode) to verify that the
recipes emit the expected shell commands without actually running brew or
touching the host.  No AWS, Tailscale, or brew calls are made.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_dry(target: str, extra_env: dict[str, str] | None = None) -> str:
    """Run ``make -n <target>`` and return its stdout.

    Parameters
    ----------
    target : str
        The Makefile target to dry-run.
    extra_env : dict[str, str] | None
        Additional environment variables to pass to make.

    Returns
    -------
    str
        Combined stdout of the dry-run invocation.
    """
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(  # noqa: S603
        ["make", "-n", target],  # noqa: S607
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout + result.stderr


def test_aws_tools_dry_run_checks_tailscale_command() -> None:
    """aws-tools dry-run must reference the tailscale command check."""
    output = _make_dry("aws-tools")
    assert "tailscale" in output


def test_aws_tools_dry_run_references_brew_on_macos() -> None:
    """aws-tools dry-run must reference brew install for macOS."""
    output = _make_dry("aws-tools")
    assert "brew" in output


def test_aws_tools_dry_run_references_linux_install_url() -> None:
    """aws-tools dry-run must reference the Linux install URL."""
    output = _make_dry("aws-tools")
    assert "tailscale.com/download/linux" in output


def test_aws_tools_dry_run_references_installed_file() -> None:
    """aws-tools dry-run must reference .aws-tools.installed for idempotency."""
    output = _make_dry("aws-tools")
    assert ".aws-tools.installed" in output


def test_aws_tools_rm_dry_run_references_installed_file() -> None:
    """aws-tools-rm dry-run must read from .aws-tools.installed."""
    output = _make_dry("aws-tools-rm")
    assert ".aws-tools.installed" in output


def test_aws_tools_rm_dry_run_references_brew_uninstall() -> None:
    """aws-tools-rm dry-run must reference brew uninstall for macOS."""
    output = _make_dry("aws-tools-rm")
    assert "brew uninstall" in output


def test_aws_tools_rm_dry_run_removes_installed_file() -> None:
    """aws-tools-rm dry-run must remove .aws-tools.installed when done."""
    output = _make_dry("aws-tools-rm")
    assert "rm" in output
    assert ".aws-tools.installed" in output


def test_aws_tools_dry_run_exits_zero() -> None:
    """make -n aws-tools must exit 0 (recipe is syntactically valid)."""
    result = subprocess.run(
        ["make", "-n", "aws-tools"],  # noqa: S607
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )
    assert result.returncode == 0, result.stderr


def test_aws_tools_rm_dry_run_exits_zero() -> None:
    """make -n aws-tools-rm must exit 0 (recipe is syntactically valid)."""
    result = subprocess.run(
        ["make", "-n", "aws-tools-rm"],  # noqa: S607
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )
    assert result.returncode == 0, result.stderr
