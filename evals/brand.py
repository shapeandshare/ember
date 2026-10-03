"""The Ember mascot, read from the brand assets and made safe to inline.

Two variants on one HTML page would share gradient ids and style classes, so
``inline`` prefixes every id, reference, and class with the variant name.
"""

from __future__ import annotations

import re
from pathlib import Path

BRAND = Path(__file__).resolve().parents[1] / "assets" / "brand" / "svg"


def mascot(variant: str) -> str:
    """Return the raw ``ember-<variant>.svg`` (``light`` or ``dark``)."""
    return (BRAND / f"ember-{variant}.svg").read_text(encoding="utf-8")


def inline(variant: str) -> str:
    """Return a mascot variant with ids and classes prefixed for inlining."""
    prefix = f"ember-{variant}"
    svg = mascot(variant)

    def prefixed(names: str) -> str:
        return " ".join(f"{prefix}-{name}" for name in names.split())

    svg = re.sub(r'id="([^"]+)"', lambda m: f'id="{prefix}-{m[1]}"', svg)
    svg = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{prefix}-{m[1]})", svg)
    svg = re.sub(
        r'aria-labelledby="([^"]+)"',
        lambda m: f'aria-labelledby="{prefixed(m[1])}"',
        svg,
    )
    svg = re.sub(r'class="([^"]+)"', lambda m: f'class="{prefixed(m[1])}"', svg)
    svg = re.sub(r"\.([A-Za-z][\w-]*)\{", lambda m: f".{prefix}-{m[1]}{{", svg)
    return svg.replace("<svg ", f'<svg class="mascot-{variant}" ', 1)
