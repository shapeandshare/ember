"""SizingStatus enum: whether an instance type is suitable for a model."""

from __future__ import annotations

from enum import StrEnum


class SizingStatus(StrEnum):
    """Suitability of an instance type for running a model.

    Attributes
    ----------
    SUPPORTED : str
        Sufficient GPU memory; recommended.
    TIGHT : str
        Marginal GPU memory; allowed with a warning.
    UNSUPPORTED : str
        Insufficient GPU memory; refused.
    """

    SUPPORTED = "supported"
    TIGHT = "tight"
    UNSUPPORTED = "unsupported"
