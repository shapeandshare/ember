"""How one probe inference ended."""

from __future__ import annotations

from enum import StrEnum


class RowStatus(StrEnum):
    """The outcome of one probe inference.

    ``OK`` answered; ``OOM`` ran out of MPS memory, with no answers; ``ERROR``
    raised any other exception, whose message the row keeps.
    """

    OK = "ok"
    OOM = "oom"
    ERROR = "error"
