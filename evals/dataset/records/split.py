"""Split: The dataset split an item is pinned to for life."""

from __future__ import annotations

from enum import StrEnum


class Split(StrEnum):
    """The dataset split an item is pinned to for life."""

    dev = "dev"
    test = "test"
