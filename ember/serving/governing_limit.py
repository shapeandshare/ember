"""Which limit is the enforced one."""

from __future__ import annotations

from enum import StrEnum


class GoverningLimit(StrEnum):
    """The limit that sets the enforced limit for a request.

    ``CAP`` when the per-request cap is enabled and not above the effective
    maximum; ``MAXIMUM`` when the cap is disabled or set above it.
    """

    CAP = "cap"
    MAXIMUM = "maximum"
