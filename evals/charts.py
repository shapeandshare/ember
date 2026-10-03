"""Bar charts, probability tracks, and the architecture diagram for the report."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .svg import circle, document, line, num, path, rect, text

Row = Mapping[str, Any]


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def wrap(value: str, width: int) -> list[str]:
    """Split ``value`` into lines of at most about ``width`` characters."""
    lines: list[str] = []
    current = ""
    for word in value.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return [*lines, current] if current else lines


def hbars(
    ident: str, title: str, desc: str, rows: Sequence[Row], *, standalone: bool
) -> str:
    """Draw horizontal accuracy bars on a 0-100% axis with optional CI whiskers.

    Each row has ``label``, ``value``, and optionally ``low``, ``high``, ``note``.
    """
    width, label_w, right = 760.0, 200.0, 150.0
    x0, x1 = label_w + 12, width - right
    top, row_h = 14.0, 34.0
    height = top + row_h * len(rows) + 34

    def x(value: float) -> float:
        return x0 + (x1 - x0) * value

    parts = []
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        parts.append(line(x(tick), top - 4, x(tick), height - 30, "c-grid"))
        parts.append(
            text(
                x(tick),
                height - 12,
                f"{tick * 100:.0f}%",
                "c-muted",
                anchor="middle",
                size=11,
            )
        )
    for index, row in enumerate(rows):
        mid = top + index * row_h + row_h / 2
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
        value = float(row["value"])
        parts.append(rect(x0, mid - 8, x(value) - x0, 16, "c-pri", rx=3))
        end = x(value)
        if row.get("low") is not None:
            low, high = x(float(row["low"])), x(float(row["high"]))
            whisker = ' stroke-width="1.6"'
            parts += [
                line(low, mid, high, mid, "c-ink-line", extra=whisker),
                line(low, mid - 6, low, mid + 6, "c-ink-line", extra=whisker),
                line(high, mid - 6, high, mid + 6, "c-ink-line", extra=whisker),
            ]
            end = max(end, high)
        label = _pct(value)
        parts.append(text(end + 8, mid + 4, label, "c-text", size=12, weight=650))
        if row.get("note"):
            parts.append(
                text(
                    end + 14 + 7.2 * len(label),
                    mid + 4,
                    str(row["note"]),
                    "c-muted",
                    size=11,
                )
            )
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )


def stacked(
    ident: str,
    title: str,
    desc: str,
    rows: Sequence[Row],
    keys: Sequence[tuple[str, str, str, str]],
    *,
    standalone: bool,
    percent: bool = False,
) -> str:
    """Draw horizontal stacked bars with a legend.

    ``rows`` hold ``label`` and ``values`` (key to number); ``keys`` are
    ``(key, legend label, fill class, text class)`` in drawing order.
    """
    width, label_w = 760.0, 200.0
    x0, x1 = label_w + 12, width - 70
    top, row_h = 44.0, 36.0
    height = top + row_h * len(rows) + 10
    totals = [sum(float(v) for v in row["values"].values()) for row in rows]
    scale = 1.0 if percent else max(totals or [1.0])
    parts = []
    legend_x = x0
    for _key, label, fill, _ in keys:
        parts.append(rect(legend_x, 14, 12, 12, fill, rx=2))
        parts.append(text(legend_x + 18, 24, label, "c-text", size=12))
        legend_x += 30 + 7.0 * len(label)
    for index, row in enumerate(rows):
        mid = top + index * row_h + row_h / 2
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
        cursor = x0
        for key, _label, fill, ink in keys:
            value = float(row["values"].get(key, 0))
            span = (x1 - x0) * value / scale if scale else 0.0
            if span <= 0:
                continue
            parts.append(rect(cursor, mid - 11, span, 22, fill))
            shown = _pct(value) if percent else f"{value:.0f}"
            if span >= 8 + 7.0 * len(shown):
                parts.append(
                    text(
                        cursor + span / 2,
                        mid + 4,
                        shown,
                        ink,
                        anchor="middle",
                        size=11,
                        weight=600,
                    )
                )
            cursor += span
        if not percent:
            parts.append(
                text(cursor + 8, mid + 4, f"{totals[index]:.0f}", "c-muted", size=11)
            )
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )


def histogram(
    ident: str,
    title: str,
    desc: str,
    values: Sequence[float],
    *,
    markers: Sequence[tuple[str, float]],
    unit: str,
    standalone: bool,
    bins: int = 16,
) -> str:
    """Draw a histogram of ``values`` with labelled vertical markers."""
    width, height = 760.0, 260.0
    x0, x1, y0, y1 = 56.0, width - 24, 40.0, height - 40
    low = min(values) if values else 0.0
    high = max(values) if values else 1.0
    step = (high - low) / bins or 1.0
    counts = [0] * bins
    for value in values:
        counts[min(int((value - low) / step), bins - 1)] += 1
    peak = max(counts or [1])

    def x(value: float) -> float:
        return x0 + (x1 - x0) * (value - low) / (high - low or 1.0)

    parts = [line(x0, y1, x1, y1, "c-axis")]
    for k in range(peak + 1):
        if k % max(1, peak // 4) == 0:
            y = y1 - (y1 - y0) * k / peak
            parts.append(line(x0, y, x1, y, "c-grid"))
            parts.append(text(x0 - 8, y + 4, str(k), "c-muted", anchor="end", size=11))
    for index, count in enumerate(counts):
        left = x0 + (x1 - x0) * index / bins
        bar_h = (y1 - y0) * count / peak
        parts.append(
            rect(left + 1.5, y1 - bar_h, (x1 - x0) / bins - 3, bar_h, "c-ter", rx=2)
        )
    for k in range(5):
        value = low + (high - low) * k / 4
        parts.append(
            text(
                x(value),
                y1 + 18,
                f"{value:.0f} {unit}",
                "c-muted",
                anchor="middle",
                size=11,
            )
        )
    for index, (label, value) in enumerate(markers):
        mx = x(value)
        parts.append(
            line(
                mx,
                y0 - 6,
                mx,
                y1,
                "c-pri-line",
                extra=' stroke-width="2" stroke-dasharray="5 3"',
            )
        )
        parts.append(
            text(
                mx + 4,
                y0 - 10 + 12 * (index % 2),
                f"{label} {value:.0f}",
                "c-text",
                size=11,
                weight=600,
            )
        )
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )


def distribution(
    ident: str,
    title: str,
    desc: str,
    rows: Sequence[tuple[str, float, str | None]],
    *,
    standalone: bool,
) -> str:
    """Draw one answer's probability per option; mark the gold and chosen options.

    ``rows`` are ``(option label, probability, role)`` with role ``gold``,
    ``chosen``, or ``None``.
    """
    width, label_w = 460.0, 146.0
    x0, x1 = label_w + 10, width - 138
    row_h, top = 26.0, 6.0
    height = top + row_h * len(rows) + 6
    tags = {"gold": ("c-pri", "gold"), "chosen": ("c-sec", "ember's pick")}
    parts = []
    for index, (label, probability, role) in enumerate(rows):
        mid = top + index * row_h + row_h / 2
        fill, tag = tags.get(role or "", ("c-ter", ""))
        parts.append(
            text(label_w, mid + 4, label, "c-text c-mono", anchor="end", size=12)
        )
        parts.append(rect(x0, mid - 8, x1 - x0, 16, "c-panel", rx=3))
        parts.append(rect(x0, mid - 8, (x1 - x0) * probability, 16, fill, rx=3))
        caption = f"{probability:.2f}" + (f" {tag}" if tag else "")
        parts.append(
            text(
                x1 + 8, mid + 4, caption, "c-text", size=12, weight=650 if tag else 400
            )
        )
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )


def track(
    ident: str, title: str, desc: str, p_true: float, gold: bool, *, standalone: bool
) -> str:
    """Place a noul answer's P(true) on the kit's no / unsure / yes zones."""
    width, height = 430.0, 84.0
    x0, x1, y = 16.0, width - 16, 38.0

    def x(value: float) -> float:
        return x0 + (x1 - x0) * value

    zones = ((0.0, 0.2, "no"), (0.2, 0.8, "unsure"), (0.8, 1.0, "yes"))
    parts = []
    for start, end, label in zones:
        parts.append(
            rect(x(start) + 1, y - 9, x(end) - x(start) - 2, 18, "c-panel", rx=4)
        )
        parts.append(
            text(
                (x(start) + x(end)) / 2,
                y + 28,
                label,
                "c-muted",
                anchor="middle",
                size=12,
            )
        )
    for mark in (0.2, 0.5, 0.8):
        parts.append(line(x(mark), y - 12, x(mark), y + 12, "c-axis"))
    gold_x = x(1.0 if gold else 0.0)
    parts.append(path(f"M{num(gold_x - 6)} {num(y - 20)} h12 l-6 8 z", "c-pri"))
    parts.append(
        text(
            gold_x,
            y - 25,
            f"gold: {'yes' if gold else 'no'}",
            "c-text",
            anchor="end" if gold else "start",
            size=12,
            weight=650,
        )
    )
    parts.append(circle(x(p_true), y, 7, "c-sec"))
    parts.append(
        text(
            x(p_true),
            y - 14,
            f"P = {p_true:.2f}",
            "c-text",
            anchor="middle",
            size=12,
            weight=650,
        )
    )
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )


def architecture(
    ident: str,
    title: str,
    desc: str,
    nodes: Sequence[Row],
    edges: Sequence[Row],
    *,
    standalone: bool,
) -> str:
    """Draw a flow: nodes left to right, a node with ``below`` under that node.

    Edges between boxes in one row run left to right; edges between a box and
    the box under it run up or down. ``style: dashed`` marks optional routes.
    """
    box_w, box_h, gap, pad = 190.0, 88.0, 128.0, 24.0
    chain = [n for n in nodes if not n.get("below")]
    where: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(chain):
        where[node["id"]] = (pad + index * (box_w + gap), pad + 18)
    for node in nodes:
        if node.get("below"):
            x, y = where[node["below"]]
            where[node["id"]] = (x, y + box_h + 78)
    width = pad * 2 + len(chain) * box_w + (len(chain) - 1) * gap
    height = max(y for _, y in where.values()) + box_h + pad
    marker = (
        f'<defs><marker id="{ident}-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M0 0 L10 5 L0 10 z" class="c-muted"/></marker></defs>'
    )
    parts = [marker]
    for edge in edges:
        (fx, fy), (tx, ty) = where[edge["from"]], where[edge["to"]]
        style = ' stroke-dasharray="6 5"' if edge.get("style") == "dashed" else ""
        arrow = f' stroke-width="1.8" marker-end="url(#{ident}-arrow)"{style}'
        if fy == ty:
            y = fy + box_h / 2
            parts.append(line(fx + box_w, y, tx - 4, y, "c-axis", extra=arrow))
            parts.append(
                text(
                    (fx + box_w + tx) / 2,
                    y - 10,
                    edge["label"],
                    "c-muted c-mono",
                    anchor="middle",
                    size=12,
                )
            )
        else:
            cx = fx + box_w / 2
            start, stop = (fy, ty + box_h + 4) if fy > ty else (fy + box_h, ty - 4)
            parts.append(line(cx, start, cx, stop, "c-axis", extra=arrow))
            parts.append(
                text(
                    cx + 10,
                    (start + stop) / 2 + 4,
                    edge["label"],
                    "c-muted c-mono",
                    size=12,
                )
            )
    for node in nodes:
        x, y = where[node["id"]]
        parts.append(
            rect(x, y, box_w, box_h, "c-panel", rx=12, extra=' stroke-width="1.4"')
        )
        parts.append(rect(x, y, 6, box_h, "c-pri", rx=3))
        parts.append(text(x + 18, y + 27, node["label"], "c-text", size=16, weight=700))
        for k, row in enumerate(wrap(node["detail"], 24)[:3]):
            parts.append(text(x + 18, y + 48 + 15 * k, row, "c-muted c-mono", size=12))
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )
