"""Load a repo-local ``.env`` without overriding the shell's environment."""

from __future__ import annotations

import os
from pathlib import Path


def load(path: Path | None = None) -> None:
    """Load ``KEY=VALUE`` lines from ``.env`` into ``os.environ`` (env wins).

    Missing files only, comments, and blank values are skipped; a variable
    already present in the environment is never overridden, so a blank
    ``.env`` entry cannot mask exported credentials.

    Parameters
    ----------
    path : Path | None, optional
        The file to load; defaults to ``.env`` in the current directory.
    """
    env_path = path if path is not None else Path(".env")
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
