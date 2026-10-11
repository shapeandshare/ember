"""Family: the family a recipe belongs to."""

from __future__ import annotations

from enum import StrEnum


class Family(StrEnum):
    """The family a recipe belongs to.

    Vision and integration recipes sit outside the headline.
    """

    coding = "coding"
    vision = "vision"
    mined_vault = "mined_vault"
    risk_trio = "risk_trio"
    harm_security = "harm_security"
    spec_kit = "spec_kit"
    grounding = "grounding"
    long_tier = "long_tier"
    boundary = "boundary"
    memory_loop = "memory_loop"
    low_priority = "low_priority"
    integration = "integration"
