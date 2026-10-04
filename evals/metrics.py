"""Scoring for the ember benchmark: calibration and classification metrics.

The scorer takes plain lists and dicts, so it needs neither torch nor
scikit-learn.

Metrics
-------
Accuracy
    Fraction of scored questions whose prediction equals the gold label. A
    ``noul`` answer predicts true at P >= 0.5; a ``score`` answer predicts the
    level nearest its expected value.
Macro-F1
    Arithmetic mean of per-class F1 (Opitz and Burst 2019, arXiv:1911.03347).
ECE / MCE
    Top-label expected and maximum calibration error over ten equal-width
    confidence bins (Guo et al. 2017). A ``noul`` answer's top-label
    confidence is max(P, 1 - P).
Brier
    Squared error between the predicted distribution and the one-hot gold
    label (Brier 1950): 0 is perfect; the worst is 2 for ``choice`` and 1 for
    ``noul``.
RPS
    Ranked probability score for ordered ``score`` questions (Epstein 1969):
    squared error between the predicted and observed cumulative
    distributions, divided by K - 1, so 0 is perfect and 1 the worst.
MAE / RMSE
    Error of the expected score against the gold level, in levels.
Coverage and accuracy at the agent-kit thresholds
    How often an answer clears the threshold at which the kit tells agents to
    act (``choice`` confidence >= 0.85; ``noul`` P >= 0.80 or <= 0.20), and
    how accurate those answers are.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

# Act-on-it thresholds published in ember/agent_kit (instructions.md, SKILL.md).
CHOICE_TRUST = 0.85
NOUL_YES = 0.80
NOUL_NO = 0.20
BINS = 10

Record = dict[str, Any]


# ###########################################################################
# Metrics
# ###########################################################################


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


# ###########################################################################
# Scoring one item
# ###########################################################################


def score_question(
    spec: Mapping[str, Any], gold: Any, answer: Mapping[str, Any] | None
) -> Record:
    """Compare one answer with its gold label.

    Raises ``ValueError`` when the answer is missing or of the wrong type,
    which means the server broke its contract rather than answered wrongly.
    """
    qtype = spec["type"]
    if answer is None or answer.get("type") != qtype:
        raise ValueError(f"expected a {qtype} answer, got {answer!r}")
    record: Record = {"type": qtype, "gold": gold}
    if qtype == "choice":
        predicted = str(answer["choice"])
        record.update(
            predicted=predicted,
            confidence=float(answer["confidence"]),
            probabilities={k: float(v) for k, v in answer["probabilities"].items()},
            correct=predicted == gold,
        )
    elif qtype == "noul":
        p_true = float(answer["noul"])
        predicted = p_true >= 0.5
        record.update(
            p_true=p_true,
            probabilities={"true": p_true, "false": round(1.0 - p_true, 10)},
            confidence=max(p_true, 1.0 - p_true),
            predicted=predicted,
            correct=predicted == gold,
        )
    else:
        levels = len(spec["criteria"])
        expected = float(answer["score"])
        predicted_level = min(levels - 1, int(expected + 0.5))
        record.update(
            expected=expected,
            predicted=predicted_level,
            probabilities=[
                float(answer["probabilities"][str(k)]) for k in range(levels)
            ],
            abs_error=abs(expected - gold),
            correct=predicted_level == gold,
        )
    return record


def score_item(item: Mapping[str, Any], answers: Mapping[str, Any]) -> Record:
    """Score every gold-labelled question of one benchmark item."""
    questions = {
        qid: score_question(item["questions"][qid], gold, answers.get(qid))
        for qid, gold in item["gold_labels"].items()
    }
    return {
        "id": item["id"],
        "category": item["category"],
        "split": item["split"],
        "correct": all(q["correct"] for q in questions.values()),
        "questions": questions,
    }


# ###########################################################################
# Summary
# ###########################################################################


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _flags(records: Sequence[Record]) -> list[bool]:
    return [bool(r["correct"]) for r in records]


def _acting(acted: Sequence[bool], correct: Sequence[bool]) -> Record:
    kept = [ok for act, ok in zip(acted, correct, strict=True) if act]
    return {
        "n": len(kept),
        "coverage": len(kept) / len(acted) if acted else 0.0,
        "accuracy": _mean([float(ok) for ok in kept]) if kept else None,
    }


def _choice(records: Sequence[Record]) -> Record | None:
    if not records:
        return None
    correct = _flags(records)
    confidences = [float(r["confidence"]) for r in records]
    ece, mce = calibration_error(confidences, correct)
    return {
        "n": len(records),
        "accuracy": _mean([float(ok) for ok in correct]),
        "accuracy_ci": bootstrap_ci([float(ok) for ok in correct]),
        "macro_f1": macro_f1(
            [f"{r['question']}:{r['predicted']}" for r in records],
            [f"{r['question']}:{r['gold']}" for r in records],
        ),
        "ece": ece,
        "mce": mce,
        "brier": brier_multiclass(
            [r["probabilities"] for r in records], [r["gold"] for r in records]
        ),
        "acting": _acting([c >= CHOICE_TRUST for c in confidences], correct),
        "reliability": reliability(confidences, correct),
    }


def _noul(records: Sequence[Record]) -> Record | None:
    if not records:
        return None
    correct = _flags(records)
    p_true = [float(r["p_true"]) for r in records]
    confidences = [float(r["confidence"]) if "confidence" in r else max(p, 1.0 - p) for r, p in zip(records, p_true)]
    ece, mce = calibration_error(confidences, correct)
    return {
        "n": len(records),
        "accuracy": _mean([float(ok) for ok in correct]),
        "accuracy_ci": bootstrap_ci([float(ok) for ok in correct]),
        "ece": ece,
        "mce": mce,
        "brier": brier_binary(p_true, [bool(r["gold"]) for r in records]),
        "acting": _acting([p >= NOUL_YES or p <= NOUL_NO for p in p_true], correct),
        "reliability": reliability(confidences, correct),
    }


def _score(records: Sequence[Record]) -> Record | None:
    if not records:
        return None
    correct = _flags(records)
    errors = [float(r["abs_error"]) for r in records]
    return {
        "n": len(records),
        "accuracy": _mean([float(ok) for ok in correct]),
        "accuracy_ci": bootstrap_ci([float(ok) for ok in correct]),
        "within_one": _mean([float(e <= 1.0) for e in errors]),
        "mae": _mean(errors),
        "mae_ci": bootstrap_ci(errors),
        "rmse": math.sqrt(_mean([e * e for e in errors])),
        "rps": ranked_probability_score(
            [r["probabilities"] for r in records], [int(r["gold"]) for r in records]
        ),
    }


def _by_question(records: Sequence[Record]) -> Record:
    grouped: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        grouped[record["question"]].append(record)
    summary: Record = {}
    for qid, rows in grouped.items():
        qtype = rows[0]["type"]
        entry: Record = {
            "type": qtype,
            "category": rows[0]["category"],
            "n": len(rows),
            "accuracy": _mean([float(ok) for ok in _flags(rows)]),
        }
        if qtype == "choice":
            gold = [r["gold"] for r in rows]
            entry["macro_f1"] = macro_f1([r["predicted"] for r in rows], gold)
            entry["brier"] = brier_multiclass([r["probabilities"] for r in rows], gold)
        elif qtype == "noul":
            entry["brier"] = brier_binary(
                [r["p_true"] for r in rows], [r["gold"] for r in rows]
            )
        else:
            entry["mae"] = _mean([r["abs_error"] for r in rows])
            entry["rps"] = ranked_probability_score(
                [r["probabilities"] for r in rows], [r["gold"] for r in rows]
            )
        summary[qid] = entry
    return summary


def _by_category(results: Sequence[Mapping[str, Any]]) -> Record:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[result["category"]].append(result)
    return {
        category: {
            "items": len(rows),
            "item_accuracy": _mean([float(r["correct"]) for r in rows]),
            "accuracy": _mean(
                [float(q["correct"]) for r in rows for q in r["questions"].values()]
            ),
        }
        for category, rows in grouped.items()
    }


def _miss(record: Record) -> Record:
    signal = {"choice": "confidence", "noul": "p_true", "score": "expected"}
    return {
        "id": record["id"],
        "question": record["question"],
        "gold": record["gold"],
        "predicted": record["predicted"],
        "signal": record[signal[record["type"]]],
    }


def rounded(value: Any) -> Any:
    """``value`` with every float rounded to four decimals, for stable JSON."""
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [rounded(v) for v in value]
    return value


def aggregate(results: Sequence[Mapping[str, Any]]) -> Record:
    """Roll scored items up into the benchmark summary."""
    records = [
        {
            **question,
            "question": qid,
            "id": result["id"],
            "category": result["category"],
        }
        for result in results
        for qid, question in result["questions"].items()
    ]
    flags = [float(ok) for ok in _flags(records)]
    summary = {
        "overall": {
            "items": len(results),
            "questions": len(records),
            "accuracy": _mean(flags),
            "accuracy_ci": bootstrap_ci(flags),
            "item_accuracy": _mean([float(r["correct"]) for r in results]),
        },
        "choice": _choice([r for r in records if r["type"] == "choice"]),
        "noul": _noul([r for r in records if r["type"] == "noul"]),
        "score": _score([r for r in records if r["type"] == "score"]),
        "questions": _by_question(records),
        "categories": _by_category(results),
        "misses": [_miss(r) for r in records if not r["correct"]],
    }
    result: Record = rounded(summary)
    return result
