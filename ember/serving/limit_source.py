"""Where an effective length limit came from."""

from __future__ import annotations

from enum import StrEnum


class LimitSource(StrEnum):
    """The origin of the effective maximum or the per-request cap.

    ``MODEL`` applies to the effective maximum only (the model's ``config.json``),
    ``MEASURED`` to the per-request cap only (the registry model's probe-measured
    default). ``FALLBACK`` and ``OPERATOR`` apply to both.
    """

    MODEL = "model"
    FALLBACK = "fallback"
    OPERATOR = "operator"
    MEASURED = "measured"
