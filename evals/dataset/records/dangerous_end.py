"""DangerousEnd: Which pole of a score scale calls for caution."""

from __future__ import annotations

from enum import StrEnum


class DangerousEnd(StrEnum):
    """Which pole of a score scale calls for caution."""

    low = "low"
    high = "high"
    none = "none"
