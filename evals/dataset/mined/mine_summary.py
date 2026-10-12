"""MineSummary: what one mining run did."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MineSummary:
    """What one mining run did.

    Parameters
    ----------
    recipe : str
        The recipe mined.
    source_commit : str
        The pinned commit.
    items_written : int
        Items for this recipe present after the run.
    candidates : int
        Notes that passed the exclusion rules.
    exclusions : dict[str, int]
        Exclusion counts by reason value.
    """

    recipe: str
    source_commit: str
    items_written: int
    candidates: int
    exclusions: dict[str, int]
