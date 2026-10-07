"""Document blocks shared by the Markdown and HTML report writers.

``evals.document`` turns a report model into sections of these blocks; each
writer renders every block type. Text fields named ``text`` or ``caption`` use
inline markup (see ``evals.markup``); ``Cell`` values and ``Card`` facts are
literal data and are always escaped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .tone import Tone


@dataclass(frozen=True)
class Para:
    """A paragraph of inline markup, or literal text when ``literal``."""

    text: str
    literal: bool = False


@dataclass(frozen=True)
class Bullets:
    """A bulleted list of inline-markup items."""

    items: tuple[str, ...]


@dataclass(frozen=True)
class Heading:
    """A subsection heading with a stable anchor."""

    text: str
    anchor: str


@dataclass(frozen=True)
class Code:
    """A literal code block."""

    text: str
    lang: str = "text"


@dataclass(frozen=True)
class Callout:
    """A toned finding: ``good``, ``warn``, or ``info``."""

    tone: Tone
    title: str
    text: str


@dataclass(frozen=True)
class Kpi:
    """One headline number."""

    label: str
    value: str
    note: str = ""
    tone: Tone = Tone.INFO


@dataclass(frozen=True)
class Kpis:
    """A row of headline numbers."""

    items: tuple[Kpi, ...]


@dataclass(frozen=True)
class Formula:
    """A formula as TeX (Markdown) and plain text (HTML)."""

    tex: str
    text: str


@dataclass(frozen=True)
class Definitions:
    """Term and definition pairs; terms are literal, definitions are markup."""

    items: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Figure:
    """A chart: ``draw(standalone)`` returns its SVG; ``text`` is an ASCII version."""

    name: str
    draw: Callable[[bool], str]
    caption: str
    alt: str
    numbered: bool = True
    text: str = ""


@dataclass(frozen=True)
class Cell:
    """A literal table cell: ``text``, ``code``, ``num``, ``good``, or ``bad``."""

    value: str
    kind: str = "text"


@dataclass(frozen=True)
class Table:
    """A table; ``row_data`` and ``filters`` power the HTML item filters."""

    headers: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]
    caption: str = ""
    anchor: str = ""
    row_data: tuple[dict[str, str], ...] = ()
    filters: tuple[tuple[str, str, tuple[str, ...]], ...] = ()
    collapse: str = ""


@dataclass(frozen=True)
class Card:
    """A boxed record, such as one miss or one recipe."""

    title: str
    tag: str
    tone: Tone
    facts: tuple[tuple[str, Cell], ...]
    body: tuple[Block, ...] = ()


@dataclass(frozen=True)
class Cards:
    """A grid of cards."""

    items: tuple[Card, ...]


@dataclass(frozen=True)
class Gallery:
    """Figures shown side by side where space allows."""

    items: tuple[Figure, ...]


@dataclass(frozen=True)
class References:
    """The numbered bibliography."""

    items: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class Section:
    """A numbered top-level section."""

    anchor: str
    number: int
    title: str
    blocks: tuple[Block, ...]


Block = (
    Para
    | Bullets
    | Heading
    | Code
    | Callout
    | Kpis
    | Formula
    | Definitions
    | Figure
    | Table
    | Card
    | Cards
    | Gallery
    | References
)


# ###########################################################################
# Cell and number helpers
# ###########################################################################


def pct(value: float | None) -> str:
    """Format a share as a percentage, or ``n/a``."""
    return "n/a" if value is None else f"{value * 100:.1f}%"


def dec(value: float | None, places: int = 3) -> str:
    """Format a number to ``places`` decimals, or ``n/a``."""
    return "n/a" if value is None else f"{value:.{places}f}"


def interval(bounds: list[float] | tuple[float, float] | None) -> str:
    """Format a 0-1 interval as ``[low, high]`` percentage points."""
    if not bounds:
        return "n/a"
    return f"[{bounds[0] * 100:.1f}, {bounds[1] * 100:.1f}]"


def cell(value: object) -> Cell:
    """Return a literal text cell."""
    return Cell(str(value))


def code(value: object) -> Cell:
    """Return a code cell."""
    return Cell(str(value), "code")


def num(value: object) -> Cell:
    """Return a right-aligned numeric cell."""
    return Cell(str(value), "num")


def mark(ok: bool) -> Cell:
    """Return a correct or incorrect status cell."""
    return Cell("correct" if ok else "incorrect", "good" if ok else "bad")
