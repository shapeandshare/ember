"""The four report tones: how a finding, KPI, or table cell reads to a reviewer."""

from __future__ import annotations

from enum import StrEnum


class Tone(StrEnum):
    """One tone for a report block: a callout, KPI, card, or cell.

    ``GOOD`` and ``BAD`` mark a result that held or was wrong; ``WARN`` marks
    one worth a second look; ``INFO`` is neutral context. The string value is
    both the CSS class the HTML writer attaches and the dict key the
    Markdown and HTML writers use to look up the tone's label and icon.
    """

    GOOD = "good"
    WARN = "warn"
    INFO = "info"
    BAD = "bad"
