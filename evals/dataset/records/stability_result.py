"""StabilityResult: computed per-recipe label stability, ready for the card."""

from __future__ import annotations

from pydantic import BaseModel


class StabilityResult(BaseModel):
    """Computed label stability for one recipe.

    Parameters
    ----------
    agreement : float
        Share of entries where the re-label agreed, 0.0–1.0.
    by_label : dict[str, float]
        Agreement per gold level, keyed by the level's index; levels without
        entries are omitted.
    unstable : list[str]
        The ids of the items that disagreed, kept for the review queue.
    rater_count : int
        Always 1: gold is single-rater, and the card says so.
    """

    agreement: float
    by_label: dict[str, float]
    unstable: list[str]
    rater_count: int = 1
