"""Accuracy and Brier against state length, binned by token count (specs/004 FR-009)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .svg import circle, document, line, path, rect, text

Bin = Mapping[str, Any]


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def tokens_chart(
    ident: str, title: str, desc: str, bins: Sequence[Bin], *, standalone: bool
) -> str:
    """Draw accuracy bars (0 to 100%) and a Brier line per state-token bin.

    Parameters
    ----------
    ident, title, desc : str
        SVG identity and accessible text.
    bins : Sequence[Bin]
        ``{low, high, n, accuracy, brier}`` per non-empty bin, ascending.
    standalone : bool
        Whether to embed the light-theme stylesheet.

    Returns
    -------
    str
        The SVG document.
    """
    width, height = 760.0, 300.0
    left, right, top, bottom = 60.0, 60.0, 30.0, 70.0
    plot_w = width - left - right
    plot_h = height - top - bottom
    slot = plot_w / max(len(bins), 1)
    parts: list[str] = []
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = top + plot_h * (1 - tick)
        parts.append(line(left, y, left + plot_w, y, "c-grid"))
        parts.append(
            text(
                left - 8, y + 4, f"{tick * 100:.0f}%", "c-muted", anchor="end", size=11
            )
        )
    brier_points: list[tuple[float, float]] = []
    for index, row in enumerate(bins):
        x = left + slot * index
        accuracy = float(row["accuracy"])
        bar_h = plot_h * accuracy
        parts.append(
            rect(x + slot * 0.15, top + plot_h - bar_h, slot * 0.7, bar_h, "c-pri")
        )
        parts.append(
            text(
                x + slot / 2,
                top + plot_h - bar_h - 6,
                f"{_pct(accuracy)} (n={row['n']})",
                "c-text",
                anchor="middle",
                size=11,
            )
        )
        label = f"{row['low']}-{row['high']}"
        parts.append(
            text(
                x + slot / 2,
                height - bottom + 18,
                label,
                "c-muted",
                anchor="middle",
                size=11,
            )
        )
        if row.get("brier") is not None:
            brier_points.append(
                (x + slot / 2, top + plot_h * (1 - min(float(row["brier"]), 1.0)))
            )
    if len(brier_points) > 1:
        d = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in brier_points)
        parts.append(path(d, "c-acc-line"))
    for px, py in brier_points:
        parts.append(circle(px, py, 3.5, "c-acc"))
    parts.append(
        text(
            width / 2,
            height - 14,
            "state tokens per item",
            "c-muted",
            anchor="middle",
            size=12,
        )
    )
    parts.append(
        text(
            left,
            16,
            "bars: accuracy · line: Brier (lower is better)",
            "c-muted",
            size=11,
        )
    )
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )
