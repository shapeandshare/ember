"""Upload built conda packages to the interim Anaconda.org channel.

The conda release builds `.conda` packages in CI
(``.github/workflows/conda-package.yml``). Publishing them is the one step Anaconda.org
cannot do without a credential — it has no OIDC, unlike PyPI — so this script keeps that
step testable: it discovers the packages, refuses to run without a token, and shells
out to ``anaconda upload`` with the token passed by environment, never on the command
line. Requires ``anaconda`` (``anaconda-client``) on ``PATH``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

TOKEN_ENV = "ANACONDA_API_TOKEN"  # noqa: S105 - an env var name, not a credential
USAGE = "usage: upload_conda_packages.py <dist-dir> --user <channel>\n"


def discover_packages(dist_dir: Path) -> list[Path]:
    """Return every `.conda` package under ``dist_dir``, sorted by path.

    Parameters
    ----------
    dist_dir : Path
        Directory to search, recursively.

    Returns
    -------
    list[Path]
        The `.conda` files found, sorted for deterministic order.
    """
    return sorted(dist_dir.rglob("*.conda"))


def upload_argv(user: str, packages: Sequence[Path]) -> list[str]:
    """Build the ``anaconda upload`` argv for a channel and its packages.

    ``--skip-existing`` makes a re-run safe: Anaconda.org package files are immutable,
    so a retry after a partial upload skips what already landed rather than failing or
    clobbering.

    Parameters
    ----------
    user : str
        The Anaconda.org channel (user or organization) to publish to.
    packages : Sequence[Path]
        The `.conda` packages to upload.

    Returns
    -------
    list[str]
        The argv to run.
    """
    return [
        "anaconda",
        "upload",
        "--user",
        user,
        "--skip-existing",
        *[str(package) for package in packages],
    ]


def require_token(env: Mapping[str, str]) -> None:
    """Raise when ``ANACONDA_API_TOKEN`` is unset or blank.

    Parameters
    ----------
    env : Mapping[str, str]
        The environment to read.

    Raises
    ------
    ValueError
        If ``ANACONDA_API_TOKEN`` is missing or empty.
    """
    if not env.get(TOKEN_ENV, "").strip():
        raise ValueError(f"{TOKEN_ENV} is not set")


def publish(
    dist_dir: Path,
    user: str,
    *,
    env: Mapping[str, str],
    run: Callable[[list[str]], int],
) -> int:
    """Upload every `.conda` package under ``dist_dir`` to ``user`` on Anaconda.org.

    Parameters
    ----------
    dist_dir : Path
        Directory holding the built `.conda` packages.
    user : str
        The Anaconda.org channel to publish to.
    env : Mapping[str, str]
        The environment carrying ``ANACONDA_API_TOKEN``.
    run : Callable[[list[str]], int]
        Runs a command and returns its exit code (injected for tests).

    Returns
    -------
    int
        ``0`` on success, ``1`` when there is nothing to upload or the upload fails.

    Raises
    ------
    ValueError
        If ``ANACONDA_API_TOKEN`` is not set.
    """
    require_token(env)
    packages = discover_packages(dist_dir)
    if not packages:
        sys.stderr.write(f"error: no .conda packages under {dist_dir}\n")
        return 1
    code = run(upload_argv(user, packages))
    if code != 0:
        sys.stderr.write(f"error: anaconda upload failed (exit {code})\n")
        return 1
    print(f"uploaded {len(packages)} package(s) to anaconda.org/{user}")
    return 0


def _run(argv: list[str]) -> int:
    """Run a command, inheriting the token from the environment, and return its code."""
    return subprocess.run(argv, check=False).returncode  # noqa: S603 - fixed argv


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point: ``upload_conda_packages.py <dist-dir> --user <channel>``."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3 or args[1] != "--user":
        sys.stderr.write(USAGE)
        return 2
    try:
        return publish(Path(args[0]), args[2], env=os.environ, run=_run)
    except ValueError as error:
        sys.stderr.write(f"error: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
