"""Exact and near-duplicate detection over normalised item states."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from .records.item import Item

NEAR_THRESHOLD = 0.85
_WHITESPACE = re.compile(r"\s+")


def normalise(state: str | dict[str, Any]) -> str:
    """Return the comparison form of a state: canonical JSON, one space, lower case."""
    text = state if isinstance(state, str) else json.dumps(state, sort_keys=True)
    return _WHITESPACE.sub(" ", text).strip().lower()


def _tokens(normalised: str) -> frozenset[str]:
    return frozenset(normalised.split(" "))


def _same_gold(a: Item, b: Item) -> bool:
    return json.dumps(a.gold_labels, sort_keys=True) == json.dumps(
        b.gold_labels, sort_keys=True
    )


def exact_duplicates(items: Sequence[Item]) -> list[tuple[str, str]]:
    """Return id pairs whose normalised states are identical."""
    seen: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []
    for item in items:
        key = normalise(item.state)
        if key in seen:
            pairs.append((seen[key], item.id))
        else:
            seen[key] = item.id
    return pairs


def near_duplicates(
    items: Sequence[Item], *, threshold: float = NEAR_THRESHOLD
) -> list[tuple[str, str]]:
    """Return id pairs with token-set Jaccard ≥ ``threshold`` and identical gold.

    A near-duplicate pair whose gold differs is a hard negative by construction
    and is not reported.
    """
    by_recipe: dict[str, list[tuple[Item, frozenset[str]]]] = defaultdict(list)
    for item in items:
        by_recipe[item.category].append((item, _tokens(normalise(item.state))))
    pairs: list[tuple[str, str]] = []
    for rows in by_recipe.values():
        for index, (a, tokens_a) in enumerate(rows):
            for b, tokens_b in rows[index + 1 :]:
                if tokens_a == tokens_b or not tokens_a or not tokens_b:
                    continue
                jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
                if jaccard >= threshold and _same_gold(a, b):
                    pairs.append((a.id, b.id))
    return pairs
