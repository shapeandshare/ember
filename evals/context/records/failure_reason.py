"""Why a probe length failed the cap rule."""

from __future__ import annotations

from enum import StrEnum


class FailureReason(StrEnum):
    """Why a length failed the FR-010 rule.

    ``MEMORY``: peak memory over the model's budget. ``OOM``: MPS ran out of
    memory. ``ACCURACY``: accuracy more than the tolerance below the 2K result.
    ``BRIER``: Brier score more than the tolerance above the 2K result.
    ``ERROR``: an inference at that length and depth raised an error, or nothing ran,
    so the cell can't be scored.
    """

    MEMORY = "memory"
    OOM = "oom"
    ACCURACY = "accuracy"
    BRIER = "brier"
    ERROR = "error"


#: Failures found at one depth, so a verdict names the depth that failed.
DEPTH_REASONS = frozenset(
    {FailureReason.ACCURACY, FailureReason.BRIER, FailureReason.ERROR}
)
