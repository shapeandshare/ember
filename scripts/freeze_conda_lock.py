"""Regenerate or verify the committed conda dependency lock.

Why: ``conda/ember-deps.conda-lock.yml`` pins the exact dependency environment the
conda release is verified against (see ``specs/008-conda-release/``). It must never
be hand-edited — this script (through ``make conda-lock`` and ``make conda-lock-check``)
shells out to conda-lock to regenerate it, or to detect that the source spec changed
and the committed lock is stale. The same run renders the per-platform explicit locks
(``conda-<platform>.lock``) that the smoke installs from, because micromamba and conda
ignore conda-lock's unified YAML.

The check run works against a throwaway copy of the lock so a stale result never
mutates the working tree: conda-lock leaves the copy untouched when the spec hash is
already locked, and rewrites it when the spec has changed.
Requires ``conda-lock`` on PATH (for example via ``uvx conda-lock``).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = Path("conda") / "lock-environment.yml"
LOCK = Path("conda") / "ember-deps.conda-lock.yml"
CHECK_LOCK = Path("conda") / "ember-deps.conda-lock.yml.check-tmp"
PLATFORMS = ("osx-arm64", "linux-64")
IN_SYNC_CODE = 4


def _lock_argv(lockfile: Path, *, check: bool) -> list[str]:
    """Build the conda-lock argv for a regenerate or check run."""
    argv = ["conda-lock"]
    if check:
        argv.append("--check-input-hash")
    argv += ["-f", str(SPEC)]
    for platform in PLATFORMS:
        argv += ["-p", platform]
    argv += ["--lockfile", str(lockfile)]
    return argv


def _render_argv(platform: str) -> list[str]:
    """Build the conda-lock argv that renders a platform's explicit lock.

    The smoke installs from the explicit render: micromamba and conda ignore the
    unified YAML and would create an empty environment.
    """
    return ["conda-lock", "render", "--kind", "explicit", "-p", platform, str(LOCK)]


def _explicit_lock(platform: str) -> Path:
    """Path of the committed explicit lock for a platform."""
    return Path(f"conda-{platform}.lock")


def _missing_explicit() -> list[str]:
    """Return the platforms whose explicit lock file is absent."""
    return [
        platform
        for platform in PLATFORMS
        if not (ROOT / _explicit_lock(platform)).exists()
    ]


def _run(argv: list[str]) -> int:
    """Run a conda-lock command from the repository root and return its code."""
    return subprocess.run(  # noqa: S603 - fixed conda-lock argv, never shell
        argv, cwd=ROOT, check=False
    ).returncode


def _verify_lock(lockfile: Path) -> list[str]:
    """Return the platforms missing from a written lock (empty when complete)."""
    lock = yaml.safe_load(lockfile.read_text(encoding="utf-8"))
    present = {package["platform"] for package in lock["package"]}
    return [platform for platform in PLATFORMS if platform not in present]


def _regenerate() -> int:
    """Regenerate the unified lock and the explicit locks the smoke consumes."""
    code = _run(_lock_argv(LOCK, check=False))
    if code != 0:
        sys.stderr.write(f"error: conda-lock failed (exit {code})\n")
        return 1
    missing = _verify_lock(ROOT / LOCK)
    if missing:
        sys.stderr.write(
            f"error: the lock is missing platforms: {', '.join(missing)}\n"
        )
        return 1
    for platform in PLATFORMS:
        code = _run(_render_argv(platform))
        if code != 0:
            sys.stderr.write(
                f"error: conda-lock render failed for {platform} (exit {code})\n"
            )
            return 1
    absent = _missing_explicit()
    if absent:
        sys.stderr.write(f"error: explicit locks missing for: {', '.join(absent)}\n")
        return 1
    print(f"conda lock up to date: {LOCK.name} + {len(PLATFORMS)} explicit locks")
    return 0


def _check() -> int:
    """Verify the committed lock matches the source spec without mutating it."""
    if not (ROOT / LOCK).exists():
        sys.stderr.write(
            f"error: {LOCK} does not exist — run `make conda-lock` first\n"
        )
        return 1
    absent = _missing_explicit()
    if absent:
        sys.stderr.write(f"error: explicit locks missing for: {', '.join(absent)}\n")
        return 1
    candidate = ROOT / CHECK_LOCK
    shutil.copyfile(ROOT / LOCK, candidate)
    try:
        code = _run(_lock_argv(CHECK_LOCK, check=True))
        unchanged = candidate.read_bytes() == (ROOT / LOCK).read_bytes()
    finally:
        candidate.unlink(missing_ok=True)
    if code == IN_SYNC_CODE or (code == 0 and unchanged):
        print(f"conda lock is in sync with {SPEC}")
        return 0
    if code == 0:
        sys.stderr.write(
            "error: the lock is stale — run `make conda-lock` and commit the result\n"
        )
        return 1
    sys.stderr.write(f"error: conda-lock check failed (exit {code})\n")
    return 1


def main() -> int:
    """Entry point; pass ``--check`` to verify, otherwise regenerate."""
    if "--check" in sys.argv[1:]:
        return _check()
    return _regenerate()


if __name__ == "__main__":
    raise SystemExit(main())
