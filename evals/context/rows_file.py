"""The append-only rows file: fsynced appends, and torn-line recovery on resume."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from .records.depth import Depth
from .records.probe_row import ProbeRow

Key = tuple[str, str, int, Depth]


def read_rows(path: Path) -> list[ProbeRow]:
    """Return the file's rows, dropping a torn last line; ``[]`` if missing."""
    if not path.exists():
        return []
    complete = path.read_text(encoding="utf-8").split("\n")[:-1]
    return [ProbeRow.model_validate_json(line) for line in complete if line.strip()]


def repair(path: Path) -> None:
    """Truncate a torn last line so appends start on a fresh line."""
    if not path.exists():
        return
    data = path.read_bytes()
    if not data or data.endswith(b"\n"):
        return
    with path.open("r+b") as handle:
        handle.truncate(data.rfind(b"\n") + 1)
        handle.flush()
        os.fsync(handle.fileno())


def append_row(path: Path, row: ProbeRow) -> None:
    """Append one row, then flush and fsync it."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(row.model_dump_json() + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def pending(planned: Iterable[Key], rows: Iterable[ProbeRow]) -> list[Key]:
    """Return the planned keys not yet recorded, in order."""
    done = {row.key for row in rows}
    return [key for key in planned if key not in done]
