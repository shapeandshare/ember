"""CapSource enum: origin of a request-length cap value."""

from __future__ import annotations

from enum import StrEnum


class CapSource(StrEnum):
    """Origin of a per-request token cap value.

    Matches the ``LimitSource`` vocabulary in ``ember/serving/limit_source.py``.

    Attributes
    ----------
    MEASURED : str
        Cap was measured by the long-context probe.
    FALLBACK : str
        Cap is the pre-declared fallback, used until the probe runs.
    """

    MEASURED = "measured"
    FALLBACK = "fallback"
