"""Run provenance shared by the eval runners: git state, host, and model spec."""

from __future__ import annotations

import importlib.metadata
import platform
import subprocess
from pathlib import Path
from typing import Any

from ember import models

#: The checkout root (``evals/eval/provenance.py`` -> ``parents[2]``).
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Distributions whose installed versions a run records.
PACKAGES = ("ember-advise", "torch", "transformers", "mcp")


def _command(argv: list[str]) -> str | None:
    try:
        out = subprocess.check_output(  # noqa: S603 - fixed argv, no shell
            argv, cwd=str(REPO_ROOT), stderr=subprocess.DEVNULL, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.strip()


def git_hash() -> str:
    """Return the checkout's short commit hash, or ``"unknown"`` outside git."""
    return _command(["git", "rev-parse", "--short", "HEAD"]) or "unknown"


def git_dirty() -> bool:
    """Return whether the checkout has uncommitted changes.

    ``True`` when ``git status --porcelain`` prints anything, and also when git
    can't report at all, so an unknown tree never counts as clean.
    """
    status = _command(["git", "status", "--porcelain"])
    return status is None or bool(status)


def cpu() -> str:
    """Return the CPU brand string, falling back to ``platform.processor()``."""
    brand = _command(["sysctl", "-n", "machdep.cpu.brand_string"])
    return brand or platform.processor() or "unknown"


def ram_bytes() -> int | None:
    """Return the machine's physical memory in bytes, or ``None`` if unknown."""
    out = _command(["sysctl", "-n", "hw.memsize"])
    return int(out) if out and out.isdigit() else None


def host_info() -> dict[str, Any]:
    """Return the platform, CPU, Python version, and installed package versions."""
    packages: dict[str, str] = {}
    for name in PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return {
        "platform": platform.platform(),
        "cpu": cpu(),
        "python": platform.python_version(),
        "packages": packages,
    }


def model_spec_info(model_dir: str) -> dict[str, str | None]:
    """Return the registry entry a model directory belongs to, or ``{}``."""
    name = Path(model_dir).name
    for spec in models.REGISTRY.values():
        if name in (spec.dir_name, spec.revision):
            return {
                "name": spec.name,
                "repo": spec.repo,
                "params": spec.params,
                "revision": spec.revision,
            }
    return {}
