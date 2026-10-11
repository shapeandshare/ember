"""ItemKind: The role an item plays in its recipe's composition (specs/004 FR-026)."""

from __future__ import annotations

from enum import StrEnum


class ItemKind(StrEnum):
    """The role an item plays in its recipe's composition (specs/004 FR-026)."""

    positive = "positive"
    negative = "negative"
    control = "control"
    hard_negative = "hard_negative"
    near_miss = "near_miss"
    adversarial = "adversarial"
    insufficient_context = "insufficient_context"
    variant = "variant"
    long_tier = "long_tier"
