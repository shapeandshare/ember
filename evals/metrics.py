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
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from . import metrics_phase0
from .metric_functions import (
    bootstrap_ci,
    brier_binary,
    brier_multiclass,
    calibration_error,
    macro_f1,
    ranked_probability_score,
    reliability,
)

# Act-on-it thresholds published in ember/agent_kit (instructions.md, SKILL.md).
CHOICE_TRUST = 0.85
NOUL_YES = 0.80
NOUL_NO = 0.20

Record = dict[str, Any]


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
    confidences = [
        float(r["confidence"]) if "confidence" in r else max(p, 1.0 - p)
        for r, p in zip(records, p_true, strict=True)
    ]
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
    """Roll scored items up into the benchmark summary.

    ``overall`` covers the headline recipes only; the vision (capability)
    recipes, risk metrics, token-length bins, variant consistency, per-source
    accuracy, and tiers are separate blocks (specs/004 Phase 0).
    """
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
    headline_results = [
        r for r in results if metrics_phase0.is_headline(str(r["category"]))
    ]
    headline = [r for r in records if metrics_phase0.is_headline(str(r["category"]))]
    flags = [float(ok) for ok in _flags(headline)]
    summary = {
        "overall": {
            "items": len(headline_results),
            "questions": len(headline),
            "accuracy": _mean(flags),
            "accuracy_ci": bootstrap_ci(flags),
            "item_accuracy": _mean([float(r["correct"]) for r in headline_results]),
        },
        "capability": metrics_phase0.capability(results),
        "choice": _choice([r for r in records if r["type"] == "choice"]),
        "noul": _noul([r for r in records if r["type"] == "noul"]),
        "score": _score([r for r in records if r["type"] == "score"]),
        "questions": _by_question(records),
        "categories": _by_category(results),
        "risk": metrics_phase0.risk(results),
        "tokens": metrics_phase0.tokens(results),
        "consistency": metrics_phase0.consistency(results),
        "by_source_kind": metrics_phase0.by_source_kind(results),
        "tiers": metrics_phase0.tiers(results),
        "misses": [_miss(r) for r in records if not r["correct"]],
    }
    result: Record = rounded(summary)
    return result
