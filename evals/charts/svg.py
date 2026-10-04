"""Small SVG toolkit for the benchmark report figures.

Charts draw with semantic classes (``c-pri``, ``c-grid``, ...). A standalone
figure embeds a light stylesheet and its own background card, so it reads the
same on any page, including GitHub's light and dark themes. An inline figure
leaves styling to the host HTML document, which maps the classes onto its light
or dark theme.
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape

FONT = "system-ui, -apple-system, sans-serif"
MONO = "ui-monospace, SF Mono, Menlo, Cascadia Code, Consolas, monospace"

# Ember palette (assets/brand/tokens.css and the mascot gradients).
LIGHT = {
    "bg": "#FFF8EB",
    "panel": "#FCEFDD",
    "text": "#201922",
    "muted": "#715568",
    "grid": "#EADBD9",
    "axis": "#B8969F",
    "pri": "#603050",
    "sec": "#D65E64",
    "ter": "#C7A4E9",
    "acc": "#FF722F",
}
DARK = {
    "bg": "#201922",
    "panel": "#2A2030",
    "text": "#FFF8EB",
    "muted": "#D8BFCB",
    "grid": "#3B2E3E",
    "axis": "#98658F",
    "pri": "#FFC24D",
    "sec": "#EE8B79",
    "ter": "#A88CC9",
    "acc": "#FF8B52",
}

# class -> (CSS property, palette token)
CLASSES = {
    "c-bg": ("fill", "bg"),
    "c-panel": ("fill", "panel"),
    "c-text": ("fill", "text"),
    "c-muted": ("fill", "muted"),
    "c-on-pri": ("fill", "bg"),
    "c-pri": ("fill", "pri"),
    "c-sec": ("fill", "sec"),
    "c-ter": ("fill", "ter"),
    "c-acc": ("fill", "acc"),
    "c-grid": ("stroke", "grid"),
    "c-axis": ("stroke", "axis"),
    "c-ref": ("stroke", "muted"),
    "c-ink-line": ("stroke", "text"),
    "c-pri-line": ("stroke", "pri"),
    "c-sec-line": ("stroke", "sec"),
    "c-ter-line": ("stroke", "ter"),
    "c-acc-line": ("stroke", "acc"),
}


def rules(value: Callable[[str], str], scope: str = "") -> str:
    """Return CSS mapping every chart class onto ``value(token)``."""
    prefix = f"{scope} " if scope else ""
    css = [
        f"{prefix}.{cls}{{{prop}:{value(token)}}}"
        for cls, (prop, token) in CLASSES.items()
    ]
    css.append(f"{prefix}.c-ref{{stroke-dasharray:5 4}}")
    css.append(f"{prefix}text{{font-family:{FONT}}}")
    css.append(f"{prefix}.c-mono{{font-family:{MONO}}}")
    return "".join(css)


def num(value: float) -> str:
    """Format a coordinate compactly."""
    return f"{value:.1f}".removesuffix(".0")


def rect(
    x: float, y: float, w: float, h: float, cls: str, *, rx: float = 0, extra: str = ""
) -> str:
    """Return a ``<rect>``."""
    corner = f' rx="{num(rx)}"' if rx else ""
    return (
        f'<rect x="{num(x)}" y="{num(y)}" width="{num(max(w, 0))}" '
        f'height="{num(max(h, 0))}"{corner} class="{cls}"{extra}/>'
    )


def line(
    x1: float, y1: float, x2: float, y2: float, cls: str, *, extra: str = ""
) -> str:
    """Return a ``<line>``."""
    return (
        f'<line x1="{num(x1)}" y1="{num(y1)}" x2="{num(x2)}" y2="{num(y2)}" '
        f'class="{cls}"{extra}/>'
    )


def circle(cx: float, cy: float, r: float, cls: str, *, extra: str = "") -> str:
    """Return a ``<circle>``."""
    return f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" class="{cls}"{extra}/>'


def path(d: str, cls: str, *, extra: str = "") -> str:
    """Return a ``<path>``."""
    return f'<path d="{d}" class="{cls}"{extra}/>'


def text(
    x: float,
    y: float,
    value: str,
    cls: str = "c-text",
    *,
    anchor: str = "start",
    size: float = 12,
    weight: int = 400,
    extra: str = "",
) -> str:
    """Return an escaped ``<text>``."""
    bold = f' font-weight="{weight}"' if weight != 400 else ""
    return (
        f'<text x="{num(x)}" y="{num(y)}" class="{cls}" font-size="{num(size)}" '
        f'text-anchor="{anchor}"{bold}{extra}>{escape(value)}</text>'
    )


def document(
    ident: str,
    width: float,
    height: float,
    title: str,
    desc: str,
    body: str,
    *,
    standalone: bool,
) -> str:
    """Wrap ``body`` in an accessible root ``<svg>`` with a viewBox only."""
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {num(width)} '
        f'{num(height)}" role="img" aria-labelledby="{ident}-t {ident}-d" '
        f'class="chart" font-family="{FONT}">'
        f'<title id="{ident}-t">{escape(title)}</title>'
        f'<desc id="{ident}-d">{escape(desc)}</desc>'
    )
    if standalone:
        head += f"<style>{rules(lambda token: LIGHT[token])}</style>"
        head += rect(0, 0, width, height, "c-bg", rx=14)
    return f"{head}{body}</svg>"
