"""Per-item scores, paired deltas, and the sizing-gate math (research R10)."""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..metrics import (
    bootstrap_ci,
    brier_binary,
    brier_multiclass,
    calibration_error,
    score_question,
)

#: Question types the rule gates on; ``score`` questions are recorded, not gated.
GATED_TYPES = frozenset({"noul", "choice"})


@dataclass(frozen=True)
class ItemScore:
    """One item's accuracy and Brier over its gated questions."""

    accuracy: float
    brier: float
    confidences: tuple[float, ...]
    correct: tuple[bool, ...]


def item_scores(item: Mapping[str, Any], answers: Mapping[str, Any]) -> ItemScore:
    """Score an item's ``noul`` and ``choice`` questions.

    Raises
    ------
    ValueError
        If an answer is missing or mistyped, or the item has no gated question.
    """
    correct: list[bool] = []
    confidences: list[float] = []
    briers: list[float] = []
    for qid, gold in item["gold_labels"].items():
        spec = item["questions"][qid]
        if spec["type"] not in GATED_TYPES:
            continue
        record = score_question(spec, gold, answers.get(qid))
        correct.append(bool(record["correct"]))
        confidences.append(float(record["confidence"]))
        if spec["type"] == "noul":
            briers.append(brier_binary([record["p_true"]], [bool(gold)]))
        else:
            briers.append(brier_multiclass([record["probabilities"]], [gold]))
    if not correct:
        raise ValueError(f"item {item['id']} has no noul or choice question")
    return ItemScore(
        accuracy=statistics.fmean(correct),
        brier=statistics.fmean(briers),
        confidences=tuple(confidences),
        correct=tuple(correct),
    )


def paired_deltas(base: Mapping[str, float], other: Mapping[str, float]) -> list[float]:
    """Return ``other - base`` for each item in both, ordered by item id."""
    return [other[key] - base[key] for key in sorted(base.keys() & other.keys())]


def delta_ci(
    deltas: Sequence[float], *, resamples: int, level: float, seed: int
) -> tuple[float, float]:
    """Percentile bootstrap interval for the mean delta."""
    return bootstrap_ci(list(deltas), resamples=resamples, level=level, seed=seed)


def cell_ece(confidences: Sequence[float], correct: Sequence[bool]) -> float:
    """Top-label ECE over a cell's pooled questions (reported, not gated)."""
    return calibration_error(list(confidences), list(correct))[0]


def projected_half_width(deltas: Sequence[float]) -> float:
    """Return ``1.96 * sd(deltas) / sqrt(n)``, the sizing gate's half-width.

    Uses the sample standard deviation; fewer than two deltas size nothing, so
    the result is infinite.
    """
    if len(deltas) < 2:
        return math.inf
    return 1.96 * statistics.stdev(deltas) / math.sqrt(len(deltas))
