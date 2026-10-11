"""LicenceClass: how an external dataset's licence bears on redistribution here."""

from __future__ import annotations

from enum import StrEnum


class LicenceClass(StrEnum):
    """How an external dataset's licence bears on redistribution in this repository."""

    permissive = "permissive"
    share_alike = "share_alike"
    custom_permissive = "custom_permissive"
    non_commercial = "non_commercial"
    research_only = "research_only"
    gated = "gated"
    composite = "composite"
    unconfirmed = "unconfirmed"
