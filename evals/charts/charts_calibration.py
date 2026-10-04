"""Calibration figures for the benchmark report.

See ``evals.document`` for the section order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .charts import wrap
from .svg import circle, document, line, num, path, rect, text

Row = Mapping[str, Any]
_LEGEND_Y = 22.0


def _legend(x: float, entries: Sequence[tuple[str, str]]) -> str:
    """Draw ``(kind, label)`` legend entries: kinds are bar, line, dash, dot, ring."""
    parts = []
    for kind, label in entries:
        if kind == "bar":
            parts.append(rect(x, _LEGEND_Y - 9, 14, 10, "c-pri", rx=2))
        elif kind == "line":
            parts.append(
                line(
                    x,
                    _LEGEND_Y - 4,
                    x + 14,
                    _LEGEND_Y - 4,
                    "c-sec-line",
                    extra=' stroke-width="3"',
                )
            )
        elif kind == "dash":
            parts.append(
                line(
                    x,
                    _LEGEND_Y - 4,
                    x + 14,
                    _LEGEND_Y - 4,
                    "c-ref",
                    extra=' stroke-width="1.6"',
                )
            )
        elif kind == "dot":
            parts.append(circle(x + 7, _LEGEND_Y - 4, 5, "c-pri"))
        elif kind == "ring":
            parts.append(
                circle(
                    x + 7,
                    _LEGEND_Y - 4,
                    5,
                    "c-sec-line",
                    extra=' fill="none" stroke-width="2"',
                )
            )
        elif kind == "ter":
            parts.append(
                line(
                    x,
                    _LEGEND_Y - 4,
                    x + 14,
                    _LEGEND_Y - 4,
                    "c-ter-line",
                    extra=' stroke-width="3"',
                )
            )
        elif kind == "pri":
            parts.append(
                line(
                    x,
                    _LEGEND_Y - 4,
                    x + 14,
                    _LEGEND_Y - 4,
                    "c-pri-line",
                    extra=' stroke-width="3"',
                )
            )
        parts.append(text(x + 20, _LEGEND_Y, label, "c-text", size=11))
        x += 34 + 6.2 * len(label)
    return "".join(parts)


def _axes(
    x0: float, x1: float, y0: float, y1: float, *, x_label: str, y_label: str
) -> str:
    parts = []
    for k in range(6):
        tick = k / 5
        xx, yy = x0 + (x1 - x0) * tick, y1 - (y1 - y0) * tick
        parts.append(line(xx, y0, xx, y1, "c-grid"))
        parts.append(line(x0, yy, x1, yy, "c-grid"))
        parts.append(
            text(xx, y1 + 16, f"{tick:.1f}", "c-muted", anchor="middle", size=11)
        )
        parts.append(
            text(x0 - 8, yy + 4, f"{tick:.1f}", "c-muted", anchor="end", size=11)
        )
    parts.append(
        text(
            (x0 + x1) / 2,
            y1 + 36,
            x_label,
            "c-text",
            anchor="middle",
            size=12,
            weight=600,
        )
    )
    cy = (y0 + y1) / 2
    parts.append(
        text(
            x0 - 40,
            cy,
            y_label,
            "c-text",
            anchor="middle",
            size=12,
            weight=600,
            extra=f' transform="rotate(-90 {num(x0 - 40)} {num(cy)})"',
        )
    )
    return "".join(parts)


def reliability(
    ident: str,
    title: str,
    desc: str,
    bins: Sequence[Row],
    *,
    ece: float,
    mce: float,
    standalone: bool,
) -> str:
    """Draw a reliability diagram: accuracy per confidence bin against the diagonal."""
    width, height = 620.0, 480.0
    x0, x1, y0, y1 = 70.0, width - 24, 48.0, height - 66

    def x(value: float) -> float:
        return x0 + (x1 - x0) * value

    def y(value: float) -> float:
        return y1 - (y1 - y0) * value

    parts = [
        _legend(
            x0,
            [
                ("bar", "accuracy"),
                ("line", "mean confidence"),
                ("dash", "perfect calibration"),
            ],
        ),
        _axes(x0, x1, y0, y1, x_label="Top-label confidence", y_label="Accuracy"),
        line(x(0), y(0), x(1), y(1), "c-ref", extra=' stroke-width="1.6"'),
    ]
    for row in bins:
        left, right = x(float(row["low"])) + 3, x(float(row["high"])) - 3
        accuracy, confidence = float(row["accuracy"]), float(row["confidence"])
        if accuracy < confidence:
            parts.append(
                rect(
                    left,
                    y(confidence),
                    right - left,
                    y(accuracy) - y(confidence),
                    "c-sec",
                    extra=' fill-opacity="0.22"',
                )
            )
        parts.append(
            rect(
                left,
                y(accuracy),
                right - left,
                y1 - y(accuracy),
                "c-pri",
                extra=' fill-opacity="0.88"',
            )
        )
        parts.append(
            line(
                left,
                y(confidence),
                right,
                y(confidence),
                "c-sec-line",
                extra=' stroke-width="3"',
            )
        )
        top = min(y(accuracy), y(confidence))
        parts.append(
            text(
                (left + right) / 2,
                top - 6,
                f"n={row['n']}",
                "c-muted",
                anchor="middle",
                size=10,
            )
        )
    parts.append(rect(x0 + 10, y0 + 10, 168, 26, "c-panel", rx=6))
    parts.append(
        text(
            x0 + 20,
            y0 + 28,
            f"ECE {ece:.3f}   MCE {mce:.3f}",
            "c-text",
            size=12,
            weight=650,
        )
    )
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )


def coverage(
    ident: str,
    title: str,
    desc: str,
    points: Sequence[Row],
    kit: Sequence[Row],
    *,
    standalone: bool,
) -> str:
    """Draw coverage and accuracy as the confidence threshold rises."""
    width, height = 620.0, 440.0
    x0, x1, y0, y1 = 70.0, width - 24, 48.0, height - 66

    def x(value: float) -> float:
        return x0 + (x1 - x0) * value

    def y(value: float) -> float:
        return y1 - (y1 - y0) * value

    parts = [
        _legend(
            x0,
            [
                ("ter", "coverage: share of answers acted on"),
                ("pri", "accuracy of those answers"),
            ],
        ),
        _axes(x0, x1, y0, y1, x_label="Confidence threshold", y_label="Share"),
    ]
    for key, cls in (("coverage", "c-ter-line"), ("accuracy", "c-pri-line")):
        d = " ".join(
            f"{'M' if i == 0 else 'L'}{num(x(p['threshold']))} {num(y(p[key]))}"
            for i, p in enumerate(points)
        )
        parts.append(path(d, cls, extra=' fill="none" stroke-width="2.6"'))
    for mark in kit:
        threshold = float(mark["threshold"])
        nearest = min(points, key=lambda p: abs(p["threshold"] - threshold))
        mx = x(threshold)
        parts.append(line(mx, y0, mx, y1, "c-ref", extra=' stroke-width="1.4"'))
        parts.append(
            text(
                mx - 6,
                y1 - 10,
                f"{mark['label']} {threshold:.2f}",
                "c-text",
                anchor="end",
                size=12,
                weight=650,
            )
        )
        for key, cls in (("coverage", "c-ter"), ("accuracy", "c-pri")):
            py = y(nearest[key])
            parts.append(circle(mx, py, 5, cls))
            parts.append(
                text(
                    mx + 9,
                    py + 16,
                    f"{key} {nearest[key] * 100:.0f}%",
                    "c-text",
                    size=12,
                    weight=650,
                )
            )
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )


def heatmap(
    ident: str,
    title: str,
    desc: str,
    labels: Sequence[str],
    matrix: Sequence[Sequence[int]],
    *,
    standalone: bool,
) -> str:
    """Draw a confusion matrix: rows are gold labels, columns are predictions."""
    n = len(labels)
    cell = 56.0 if n <= 4 else 50.0
    longest = max(len(label) for label in labels)
    natural = 22 + 6.6 * longest + n * cell + 24 + 5.2 * longest
    width = max(natural, 400.0)
    left = 22 + 6.6 * longest + (width - natural) / 2
    top = 40 + 4.6 * longest
    height = top + n * cell + 20
    peak = max((v for row in matrix for v in row), default=1) or 1
    parts = [text(12, 20, "rows: gold   columns: ember's answer", "c-muted", size=11)]
    for j, label in enumerate(labels):
        cx, cy = left + j * cell + cell / 2, top - 8
        parts.append(
            text(
                cx,
                cy,
                label,
                "c-text c-mono",
                size=11,
                extra=f' transform="rotate(-40 {num(cx)} {num(cy)})"',
            )
        )
    for i, row in enumerate(matrix):
        parts.append(
            text(
                left - 10,
                top + i * cell + cell / 2 + 4,
                labels[i],
                "c-text c-mono",
                anchor="end",
                size=11,
            )
        )
        for j, count in enumerate(row):
            cx, cy = left + j * cell, top + i * cell
            share = count / peak
            if count:
                opacity = f' fill-opacity="{0.10 + 0.90 * share:.2f}"'
                parts.append(
                    rect(
                        cx + 2, cy + 2, cell - 4, cell - 4, "c-pri", rx=6, extra=opacity
                    )
                )
            else:
                parts.append(rect(cx + 2, cy + 2, cell - 4, cell - 4, "c-panel", rx=6))
            if i == j:
                parts.append(
                    rect(
                        cx + 2,
                        cy + 2,
                        cell - 4,
                        cell - 4,
                        "c-ink-line",
                        rx=6,
                        extra=' fill="none" stroke-width="1.6"',
                    )
                )
            ink = "c-on-pri" if share > 0.5 else "c-text"
            parts.append(
                text(
                    cx + cell / 2,
                    cy + cell / 2 + 5,
                    str(count),
                    ink,
                    anchor="middle",
                    size=14,
                    weight=650,
                )
            )
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )


def strip(
    ident: str,
    title: str,
    desc: str,
    levels: Sequence[str],
    points: Sequence[Row],
    means: Sequence[Row],
    *,
    threshold: tuple[str, float] | None,
    standalone: bool,
) -> str:
    """Draw expected scores grouped by gold level, with per-level means."""
    k = len(levels)
    col_w, left = 150.0, 64.0
    width = left + k * col_w + 24
    y0, y1 = 48.0, 330.0
    height = y1 + 64

    def y(value: float) -> float:
        return y1 - (y1 - y0) * value / (k - 1)

    parts = [
        _legend(
            left,
            [
                ("dot", "rounds to the gold level"),
                ("ring", "misses it"),
                ("dash", "gold level"),
                ("line", "mean"),
            ],
        )
    ]
    for level in range(k):
        parts.append(line(left, y(level), width - 24, y(level), "c-grid"))
        parts.append(
            text(left - 10, y(level) + 4, str(level), "c-muted", anchor="end", size=11)
        )
    cy = (y0 + y1) / 2
    parts.append(
        text(
            18,
            cy,
            "Expected score",
            "c-text",
            anchor="middle",
            size=12,
            weight=600,
            extra=f' transform="rotate(-90 18 {num(cy)})"',
        )
    )
    for level, label in enumerate(levels):
        cx = left + level * col_w + col_w / 2
        parts.append(
            line(
                cx - col_w / 2 + 14,
                y(level),
                cx + col_w / 2 - 14,
                y(level),
                "c-ref",
                extra=' stroke-width="1.6"',
            )
        )
        members = [p for p in points if p["gold"] == level]
        for index, point in enumerate(members):
            px = cx + (index * 29) % 72 - 36
            py = y(float(point["expected"]))
            if point["correct"]:
                parts.append(circle(px, py, 5.5, "c-pri", extra=' fill-opacity="0.85"'))
            else:
                parts.append(
                    circle(
                        px,
                        py,
                        5.5,
                        "c-sec-line",
                        extra=' fill="none" stroke-width="2.2"',
                    )
                )
        for row, part in enumerate(wrap(label, 18)[:2]):
            parts.append(
                text(
                    cx,
                    y1 + 22 + 14 * row,
                    part,
                    "c-text",
                    anchor="middle",
                    size=11,
                    weight=600 if row == 0 else 400,
                )
            )
    for mean in means:
        if mean["mean_expected"] is None:
            continue
        cx = left + mean["level"] * col_w + col_w / 2
        my = y(float(mean["mean_expected"]))
        parts.append(
            line(
                cx - 30,
                my,
                cx + 30,
                my,
                "c-sec-line",
                extra=' stroke-width="3.2" stroke-linecap="round"',
            )
        )
        parts.append(
            text(
                cx + 34,
                my + 4,
                f"{mean['mean_expected']:.2f}",
                "c-text",
                size=11,
                weight=650,
            )
        )
    if threshold is not None:
        label, value = threshold
        ty = y(value)
        parts.append(
            line(
                left,
                ty,
                width - 24,
                ty,
                "c-acc-line",
                extra=' stroke-width="1.8" stroke-dasharray="8 5"',
            )
        )
        parts.append(text(left + 6, ty - 6, label, "c-text", size=11, weight=650))
    return document(
        ident, width, height, title, desc, "".join(parts), standalone=standalone
    )
