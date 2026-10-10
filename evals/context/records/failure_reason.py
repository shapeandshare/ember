"""Why a probe length failed the cap rule."""

from __future__ import annotations

from enum import StrEnum


class FailureReason(StrEnum):
    """Why a length failed the FR-010 rule.

    ``MEMORY``: peak memory over the model's budget. ``OOM``: MPS ran out of
    memory. ``ACCURACY``: accuracy more than the tolerance below the 2K result.
    ``BRIER``: Brier score more than the tolerance above the 2K result.
    """

    MEMORY = "memory"
    OOM = "oom"
    ACCURACY = "accuracy"
    BRIER = "brier"


#: Failures judged at one depth, so a verdict names the depth that failed.
QUALITY_REASONS = frozenset({FailureReason.ACCURACY, FailureReason.BRIER})
