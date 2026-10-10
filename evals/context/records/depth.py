"""Where the evidence sits inside a padded state."""

from __future__ import annotations

from enum import StrEnum


class Depth(StrEnum):
    """The evidence's position in a padded state (research R9).

    ``START`` puts no filler before the evidence, ``MIDDLE`` splits the filler
    evenly around it, and ``END`` puts no filler after it, so the evidence sits
    right before the schema.
    """

    START = "start"
    MIDDLE = "middle"
    END = "end"
