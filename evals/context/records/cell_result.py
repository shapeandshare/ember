"""One summary cell: a model at one length and depth."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .depth import Depth


class CellResult(BaseModel):
    """Scores for one (model, length, depth), with deltas paired against 2K.

    Deltas pair the same items at the same depth; the 2K cells have deltas of 0.
    """

    model_config = ConfigDict(frozen=True)

    model: str
    length: int
    depth: Depth
    exploratory: bool
    n_items: int = Field(ge=0)
    accuracy: float
    brier: float
    ece: float
    delta_accuracy: float
    delta_accuracy_ci: tuple[float, float]
    delta_brier: float
    delta_brier_ci: tuple[float, float]
