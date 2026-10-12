"""Deterministic item ids from a recipe and a source artefact."""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def item_id(category: str, artefact: str) -> str:
    """Return the deterministic item id for a source artefact."""
    base = artefact.removesuffix(".md")
    slug = _SLUG_RE.sub("-", base.lower()).strip("-")
    return f"{category}-{slug}"
