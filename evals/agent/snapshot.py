"""File-hash snapshot of a sandbox repository at one moment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    """File hashes and git position of the repo at one moment."""

    files: dict[str, str]
    head: str
    commits: int
