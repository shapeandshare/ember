"""Verdict: A data-source register row's verdict on an external dataset."""

from __future__ import annotations

from enum import StrEnum


class Verdict(StrEnum):
    """A data-source register row's verdict on an external dataset."""

    candidate = "candidate"
    conditional = "conditional"
    excluded = "excluded"
    unconfirmed = "unconfirmed"
    used = "used"
