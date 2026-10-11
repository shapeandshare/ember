"""Pure metric formulas for the ember benchmark.

Shared by the scorer, the long-context probe, and the risk metrics.

Split out of ``evals/metrics.py`` (Article X §10.3). Definitions follow the
sources cited in ``evals/report_text.METRICS``.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Any

BINS = 10

Record = dict[str, Any]


def macro_f1(predicted: Sequence[str], gold: Sequence[str]) -> float:
    """Arithmetic mean of per-class F1 over every class seen in either list."""
    pairs = list(zip(predicted, gold, strict=True))
    classes = set(predicted) | set(gold)
    if not classes:
        return 0.0
    total = 0.0
    for label in classes:
        tp = sum(p == label and g == label for p, g in pairs)
        fp = sum(p == label and g != label for p, g in pairs)
        fn = sum(p != label and g == label for p, g in pairs)
        total += 2 * tp / (2 * tp + fp + fn)
    return total / len(classes)


def reliability(
    confidences: Sequence[float], correct: Sequence[bool], *, bins: int = BINS
) -> list[Record]:
    """Per-bin count, mean confidence, and accuracy; empty bins are omitted."""
    counts = [0] * bins
    hits = [0] * bins
    sums = [0.0] * bins
    for confidence, ok in zip(confidences, correct, strict=True):
        index = min(int(confidence * bins), bins - 1)
        counts[index] += 1
        hits[index] += ok
        sums[index] += confidence
    return [
        {
            "low": b / bins,
            "high": (b + 1) / bins,
            "n": counts[b],
            "confidence": sums[b] / counts[b],
            "accuracy": hits[b] / counts[b],
        }
        for b in range(bins)
        if counts[b]
    ]


def calibration_error(
    confidences: Sequence[float], correct: Sequence[bool], *, bins: int = BINS
) -> tuple[float, float]:
    """Top-label ECE and MCE: weighted mean and worst bin |accuracy - confidence|."""
    if not confidences:
        return (0.0, 0.0)
    rows = reliability(confidences, correct, bins=bins)
    gaps = [abs(row["accuracy"] - row["confidence"]) for row in rows]
    ece = sum(
        row["n"] / len(confidences) * gap for row, gap in zip(rows, gaps, strict=True)
    )
    return (ece, max(gaps))


def brier_multiclass(
    distributions: Sequence[Mapping[str, float]], gold: Sequence[str]
) -> float:
    """Mean squared error between each distribution and its one-hot gold label."""
    if not distributions:
        return 0.0
    total = 0.0
    for distribution, label in zip(distributions, gold, strict=True):
        total += sum((p - float(k == label)) ** 2 for k, p in distribution.items())
        if label not in distribution:
            total += 1.0
    return total / len(distributions)


def brier_binary(probabilities: Sequence[float], outcomes: Sequence[bool]) -> float:
    """Mean squared error between P(true) and the gold outcome."""
    if not probabilities:
        return 0.0
    pairs = zip(probabilities, outcomes, strict=True)
    return sum((p - float(y)) ** 2 for p, y in pairs) / len(probabilities)


def ranked_probability_score(
    distributions: Sequence[Sequence[float]], gold: Sequence[int]
) -> float:
    """Mean RPS of ordered-level distributions against gold levels."""
    if not distributions:
        return 0.0
    total = 0.0
    for probabilities, level in zip(distributions, gold, strict=True):
        cumulative = 0.0
        squared = 0.0
        for k in range(len(probabilities) - 1):
            cumulative += probabilities[k]
            squared += (cumulative - float(level <= k)) ** 2
        total += squared / (len(probabilities) - 1)
    return total / len(distributions)


def bootstrap_ci(
    values: Sequence[float],
    *,
    resamples: int = 1000,
    level: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap interval for the mean of ``values``."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)  # noqa: S311 - statistical resampling, not security
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(resamples))
    tail = (1.0 - level) / 2.0
    upper = min(resamples - 1, int((1.0 - tail) * resamples))
    return (means[int(tail * resamples)], means[upper])
