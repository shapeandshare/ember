"""Pad an item's evidence with filler to an exact encoded length (research R9)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .records.depth import Depth

SEPARATOR = "\n\n"
_SECANT_STEPS = 6


def _assemble(evidence: str, before: str, after: str) -> str:
    return before + SEPARATOR + evidence + SEPARATOR + after


def _padded(
    evidence: str,
    filler_ids: Sequence[int],
    tokenizer: Any,
    depth: Depth,
    tokens: int,
    offset: int,
) -> str:
    ids = list(filler_ids[offset : offset + tokens])
    if depth is Depth.START:
        before, after = [], ids
    elif depth is Depth.END:
        before, after = ids, []
    else:
        before, after = ids[: len(ids) // 2], ids[len(ids) // 2 :]
    return _assemble(
        evidence,
        tokenizer.decode(before) if before else "",
        tokenizer.decode(after) if after else "",
    )


def build_state(
    evidence: str,
    filler_ids: Sequence[int],
    tokenizer: Any,
    depth: Depth,
    target: int,
    count: Callable[[str], int],
    *,
    offset: int,
    tolerance: int = 32,
) -> str:
    """Return the evidence between two blank-line separators, padded to ``target``.

    ``count`` returns a state's full encoded request size; the result counts
    within ``[target - tolerance, target]``. Filler comes from ``filler_ids``
    starting at ``offset``, placed according to ``depth``.

    Raises
    ------
    ValueError
        If the evidence alone needs more than ``target - tolerance`` tokens, or
        no amount of filler lands in the window.
    """
    floor = target - tolerance
    base = count(_assemble(evidence, "", ""))
    if base > floor:
        raise ValueError(
            f"the evidence alone needs {base} tokens, more than the {floor} "
            f"a {target}-token cell allows"
        )
    available = len(filler_ids) - offset
    goal = (floor + target) // 2

    def state_for(tokens: int) -> str:
        return _padded(evidence, filler_ids, tokenizer, depth, tokens, offset)

    # Secant steps from the known zero-filler point usually land in one or two.
    previous = (0, base)
    tokens = min(target - base, available)
    for _ in range(_SECANT_STEPS):
        state = state_for(tokens)
        total = count(state)
        if floor <= total <= target:
            return state
        slope = (total - previous[1]) / (tokens - previous[0]) if tokens else 1.0
        previous = (tokens, total)
        step = max(0, min(available, tokens + round((goal - total) / max(slope, 0.1))))
        if step == tokens:
            break
        tokens = step
    # Count grows with filler, so bisect for an amount that lands in the window.
    low, high = 0, available
    while low <= high:
        tokens = (low + high) // 2
        state = state_for(tokens)
        total = count(state)
        if total > target:
            high = tokens - 1
        elif total < floor:
            low = tokens + 1
        else:
            return state
    raise ValueError(
        f"no amount of filler lands the state in [{floor}, {target}] tokens"
    )
