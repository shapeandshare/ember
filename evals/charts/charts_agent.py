"""Charts for the agent-in-the-loop section of the report."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .svg import document, line, rect, text

Row = Mapping[str, Any]


def diverging(
    ident: str, title: str, desc: str, rows: Sequence[Row], *, standalone: bool
) -> str:
    """Draw signed differences on a -100 to +100 point axis around zero.

    Each row has ``label``, ``value`` (a -1 to 1 difference), optional ``low``
    and ``high`` interval bounds, and an optional ``note``.
    """
    width, label_w, right = 760.0, 230.0, 96.0
    x0, x1 = label_w + 12, width - right
    top, row_h = 14.0, 34.0
    height = top + row_h * len(rows) + 34

    def x(value: float) -> float:
        return x0 + (x1 - x0) * (max(-1.0, min(1.0, value)) + 1) / 2

    parts = []
    for tick in (-1.0, -0.5, 0.0, 0.5, 1.0):
        cls = "c-axis" if tick == 0 else "c-grid"
        parts.append(line(x(tick), top - 4, x(tick), height - 30, cls))
        parts.append(
            text(
                x(tick),
                height - 12,
                f"{tick * 100:+.0f}",
                "c-muted",
                anchor="middle",
                size=11,
            )
        )
    for index, row in enumerate(rows):
        mid = top + index * row_h + row_h / 2
        value = float(row["value"])
        parts.append(
            text(
                label_w,
                mid + 4,
                str(row["label"]),
                "c-text c-mono",
                anchor="end",
                size=12,
            )
        )
        fill = "c-pri" if value >= 0 else "c-sec"
        parts.append(
            rect(min(x(0), x(value)), mid - 8, abs(x(value) - x(0)), 16, fill, rx=3)
        )
        if row.get("low") is not None:
            low, high = x(float(row["low"])), x(float(row["high"]))
            whisker = ' stroke-width="1.6"'
            parts += [
                line(low, mid, high, mid, "c-ink-line", extra=whisker),
                line(low, mid - 6, low, mid + 6, "c-ink-line", extra=whisker),
                line(high, mid - 6, high, mid + 6, "c-ink-line", extra=whisker),
            ]
        label = f"{value * 100:+.1f} pts"
        parts.append(text(x1 + 10, mid + 4, label, "c-text", size=12, weight=650))
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )
