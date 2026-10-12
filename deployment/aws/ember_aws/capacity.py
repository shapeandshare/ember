"""Capacity enum: on-demand or spot instance purchasing option."""

from __future__ import annotations

from enum import StrEnum


class Capacity(StrEnum):
    """EC2 instance purchasing option.

    Attributes
    ----------
    ON_DEMAND : str
        Standard on-demand pricing.
    SPOT : str
        Spot instance pricing (lower cost, interruptible).
    """

    ON_DEMAND = "on-demand"
    SPOT = "spot"
