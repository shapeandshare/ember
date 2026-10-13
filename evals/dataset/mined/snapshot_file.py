"""SnapshotFile: one vault file at the pinned commit."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SnapshotFile:
    """A vault file read at the pinned commit.

    Parameters
    ----------
    path : str
        The vault-relative path.
    text : str
        The file's committed text.
    """

    path: str
    text: str
