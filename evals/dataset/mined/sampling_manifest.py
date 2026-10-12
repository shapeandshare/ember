"""SamplingManifest: the recorded, reproducible description of one mine run."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .exclusion_record import ExclusionRecord


class SamplingManifest(BaseModel):
    """The committed record of one mining run.

    Parameters
    ----------
    recipe, source_commit, register_row : str
        What was mined, from where, under which register row.
    seed, count : int
        The deterministic seed and the requested pick count.
    word_floor, max_gold, distractor_count, max_candidates : int
        The declared rule constants in force for the run.
    exclusions : list[ExclusionRecord]
        Every excluded note with its reason.
    item_ids : list[str]
        The ids written into the dataset.
    """

    model_config = ConfigDict(frozen=True)

    recipe: str
    source_commit: str
    register_row: str
    seed: int
    count: int
    word_floor: int
    max_gold: int
    distractor_count: int
    max_candidates: int
    exclusions: list[ExclusionRecord]
    item_ids: list[str]
