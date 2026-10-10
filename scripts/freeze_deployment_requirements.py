"""Resolve deployment/requirements.txt's PEP 508 markers for the Outerbounds target.

``uv export`` emits a universal (multi-platform) requirements file straight from
``uv.lock``, including PEP 508 environment markers (e.g. ``; sys_platform ==
'linux'``) so the same lock covers every platform a contributor might run on.
Outerbounds' Fast Bakery requirements parser does not support environment
markers at all and rejects any line containing one (see
``vault/decisions/`` for the deploy-time failure this fixes).

This script evaluates every marker against the Outerbounds deployment's actual
target environment (Linux x86_64, CPython 3.12 — see ``deployment/flash.yaml``
and ``deployment/full.yaml``, which share this one requirements.txt) and
rewrites the file in place: lines whose marker is true for that target keep
their pinned version with the marker stripped; lines whose marker is false for
that target (e.g. ``sys_platform == 'win32'``, ``sys_platform == 'emscripten'``)
are dropped entirely. Unmarked lines pass through unchanged. This keeps
``deployment/requirements.txt`` locked to the exact versions in ``uv.lock``
rather than re-resolving them, while producing a plain, marker-free file Fast
Bakery can parse.

``uv export`` is run with ``--no-emit-project`` (see ``make deployment-requirements``
in ``shared/release.mk``) so the project's own package is deliberately absent from
the export — but Outerbounds' Fast Bakery only ``pip install``s what this file lists
and does not implicitly install the packaged source tree it copies in via
``--package-src-path .``. Without an explicit ``ember-advise`` line, the deployed
container never gets the ``[project.scripts]`` entry points (``ember``, ``gut``,
``ember-mcp``), and ``commands: [ember serve]`` in either deployment config fails
with ``ember: command not found``. This script re-adds ``ember-advise==<version>``,
pinned to the version in ``pyproject.toml``, after resolving markers.

Run via ``make deployment-requirements``, never directly against a stale file.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from packaging.markers import Marker

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_PATH = ROOT / "deployment" / "requirements.txt"
_PYPROJECT_PATH = ROOT / "pyproject.toml"
with _PYPROJECT_PATH.open("rb") as _pyproject_file:
    _PROJECT_VERSION = tomllib.load(_pyproject_file)["project"]["version"]

# The Outerbounds compute pool's environment (deployment/flash.yaml and
# deployment/full.yaml: Linux container, CUDA on x86_64 NVIDIA GPUs, CPython
# 3.12). Keep in sync with dependencies.python in both files.
_TARGET_ENVIRONMENT = {
    "implementation_name": "cpython",
    "implementation_version": "3.12.0",
    "os_name": "posix",
    "platform_machine": "x86_64",
    "platform_python_implementation": "CPython",
    "platform_release": "",
    "platform_system": "Linux",
    "platform_version": "",
    "python_full_version": "3.12.0",
    "python_version": "3.12",
    "sys_platform": "linux",
}


def _resolve_line(line: str) -> str | None:
    """Evaluate a single requirements-file line's marker against the target.

    Parameters
    ----------
    line : str
        One line from a ``uv export``-generated requirements file: a
        requirement optionally followed by `` ; <marker>``, a comment, or
        blank.

    Returns
    -------
    str | None
        The line with its marker stripped (if the marker is true, or there is
        no marker), or ``None`` if a present marker evaluates false for the
        target environment and the line should be dropped.
    """
    stripped = line.rstrip("\n")
    if not stripped.strip() or stripped.lstrip().startswith("#"):
        return stripped
    requirement, sep, marker_text = stripped.partition(";")
    if not sep:
        return stripped
    if Marker(marker_text.strip()).evaluate(_TARGET_ENVIRONMENT):
        return requirement.rstrip()
    return None


def _ensure_ember_advise_pin(lines: list[str]) -> list[str]:
    """Add ``ember-advise==<version>`` if ``--no-emit-project`` stripped it.

    Parameters
    ----------
    lines : list[str]
        Resolved requirements-file lines (markers already stripped/dropped).

    Returns
    -------
    list[str]
        ``lines`` unchanged if an ``ember-advise==`` pin is already present
        (idempotent re-runs); otherwise ``lines`` with the pin appended.
    """
    pin = f"ember-advise=={_PROJECT_VERSION}"
    if any(line.startswith("ember-advise==") for line in lines):
        return lines
    return [*lines, pin]


def main() -> int:
    """Rewrite ``deployment/requirements.txt`` with markers resolved for Linux.

    Returns
    -------
    int
        ``0`` on success; non-zero if the file is missing.
    """
    if not REQUIREMENTS_PATH.is_file():
        print(f"error: {REQUIREMENTS_PATH} does not exist", file=sys.stderr)
        return 1
    lines = REQUIREMENTS_PATH.read_text().splitlines()
    resolved = [out for line in lines if (out := _resolve_line(line)) is not None]
    resolved = _ensure_ember_advise_pin(resolved)
    REQUIREMENTS_PATH.write_text("\n".join(resolved) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
