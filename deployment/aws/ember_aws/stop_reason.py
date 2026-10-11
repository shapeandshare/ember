"""StopReason enum: why an ember instance stopped."""

from __future__ import annotations

from enum import StrEnum


class StopReason(StrEnum):
    """Reason an ember instance stopped.

    Attributes
    ----------
    OPERATOR : str
        Stopped by the operator via ``make aws-stop``.
    IDLE : str
        Stopped by the idle timer.
    SPOT_INTERRUPTION : str
        Stopped by a spot interruption.
    UNKNOWN : str
        Reason could not be determined.
    """

    OPERATOR = "operator"
    IDLE = "idle"
    SPOT_INTERRUPTION = "spot-interruption"
    UNKNOWN = "unknown"
