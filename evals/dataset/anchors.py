"""Validate a score scale's per-level rubric anchors against its question."""

from __future__ import annotations

from .records.scale import Scale


def validate_anchors(scale: Scale, criteria: list[str]) -> list[str]:
    """Return the problems with ``scale.anchors`` against ``criteria``.

    Parameters
    ----------
    scale : Scale
        The registered scale.
    criteria : list[str]
        The question's level labels, lowest first.

    Returns
    -------
    list[str]
        Human-readable problems; empty when the anchors are sound. Count
        mismatches are checked here because the criteria live on the items,
        not on the frozen ``Scale`` record.
    """
    prefix = f"{scale.category}/{scale.question}"
    if not scale.anchors:
        return [f"{prefix}: no rubric anchors declared"]
    problems: list[str] = []
    if len(scale.anchors) != len(criteria):
        problems.append(
            f"{prefix}: expected {len(criteria)} anchors, got {len(scale.anchors)}"
        )
    for index, anchor in enumerate(scale.anchors):
        if not anchor.strip():
            problems.append(f"{prefix}: level {index} anchor is empty")
    for index in range(len(scale.anchors) - 1):
        current, following = scale.anchors[index], scale.anchors[index + 1]
        if current and current == following:
            problems.append(f"{prefix}: levels {index} and {index + 1} share an anchor")
    return problems
