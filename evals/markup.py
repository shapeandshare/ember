"""Inline markup and escaping shared by the report writers.

Narrative strings use `code`, **bold**, [text](https://url), and [@key]
citations. Data from the dataset or a run is never treated as markup: writers
escape it with ``md_literal`` or ``html.escape``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from html import escape

CODE = re.compile(r"`([^`]+)`")
CITE = re.compile(r"\[@([A-Za-z0-9_-]+)\]")
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>|#])")


class Citations:
    """Number references in list order and resolve ``[@key]`` markers."""

    def __init__(self, references: Sequence[Mapping[str, str]]) -> None:
        self.numbers = {ref["key"]: i for i, ref in enumerate(references, 1)}

    def number(self, key: str) -> int:
        """Return the 1-based number of ``key``; unknown keys raise ``KeyError``."""
        return self.numbers[key]


def to_html(value: str, cites: Citations) -> str:
    """Convert inline markup to escaped HTML."""
    out = []
    for index, part in enumerate(CODE.split(value)):
        if index % 2:
            out.append(f"<code>{escape(part)}</code>")
            continue
        safe = escape(part)
        safe = CITE.sub(
            lambda m: (
                f'<a class="cite" href="#ref-{m[1]}" aria-label="Reference '
                f'{cites.number(m[1])}">[{cites.number(m[1])}]</a>'
            ),
            safe,
        )
        safe = LINK.sub(lambda m: f'<a href="{m[2]}">{m[1]}</a>', safe)
        out.append(BOLD.sub(r"<strong>\1</strong>", safe))
    return "".join(out)


def to_markdown(value: str, cites: Citations) -> str:
    """Resolve citations; the rest of the markup is already Markdown."""
    return CITE.sub(lambda m: f"[[{cites.number(m[1])}]](#ref-{m[1]})", value)


def md_literal(value: str) -> str:
    """Escape untrusted text for a Markdown paragraph or table cell."""
    return _MD_SPECIAL.sub(r"\\\1", value).replace("\n", "<br>")


def md_code(value: str) -> str:
    """Wrap ``value`` in a code span that survives backticks inside it."""
    fence = "``" if "`" in value else "`"
    pad = " " if "`" in value else ""
    return f"{fence}{pad}{value.replace('|', '&#124;')}{pad}{fence}"


def md_fence(value: str) -> str:
    """Pick a code fence that the content cannot close early."""
    return "~~~~" if "```" in value or "~~~" in value else "```"
