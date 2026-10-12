"""ExclusionReason: why a vault note was not mined."""

from __future__ import annotations

from enum import StrEnum


class ExclusionReason(StrEnum):
    """Why a vault note was not mined."""

    out_of_scope = "out_of_scope"
    non_content = "non_content"
    drift = "drift"
    tag_set_bounds = "tag_set_bounds"
    secret = "secret"
