"""Markdown helpers shared by the quick report and the run comparison."""

from __future__ import annotations

DASH = "—"


def pct(value: float | None) -> str:
    """Format a ratio as a percentage, or a dash for ``None``."""
    return DASH if value is None else f"{value * 100:.1f}%"


def num(value: float | None) -> str:
    """Format a number to three decimals, or a dash for ``None``."""
    return DASH if value is None else f"{value:.3f}"


def ci(interval: list[float] | None) -> str:
    """Format a 95% interval as percentages, or a dash when absent."""
    if not interval:
        return DASH
    return f"[{interval[0] * 100:.1f}, {interval[1] * 100:.1f}]"


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Render an aligned Markdown table; the last element is a blank line."""
    widths = [
        max([len(h), *(len(row[i]) for row in rows)]) for i, h in enumerate(headers)
    ]

    def line(cells: list[str]) -> str:
        padded = (cell.ljust(width) for cell, width in zip(cells, widths, strict=True))
        return "| " + " | ".join(padded) + " |"

    rule = "| " + " | ".join("-" * width for width in widths) + " |"
    return [line(headers), rule, *(line(row) for row in rows), ""]
