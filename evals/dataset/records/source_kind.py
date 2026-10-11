"""SourceKind: Where a benchmark item came from."""

from __future__ import annotations

from enum import StrEnum


class SourceKind(StrEnum):
    """Where a benchmark item came from."""

    authored = "authored"
    mined = "mined"
    captured = "captured"
    perturbed = "perturbed"
    templated = "templated"
    drafted = "drafted"
    imported = "imported"
