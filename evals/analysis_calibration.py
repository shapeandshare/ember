"""Calibration views for the report: coverage, confusion, and score spread."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from . import metrics
from .analysis_findings import confidence, questions_of
from .analysis_policies import TRUST, VERIFY

Record = dict[str, Any]


def coverage(items: Sequence[Record]) -> Record:
    """Return coverage and accuracy at every threshold, with the kit's marked."""
    curves: Record = {}
    kit = {
        "choice": [
            {"threshold": TRUST, "label": "trust"},
            {"threshold": VERIFY, "label": "verify"},
        ],
        "noul": [{"threshold": metrics.NOUL_YES, "label": "decisive"}],
    }
    for qtype in ("choice", "noul"):
        answers = [
            (confidence(q), bool(q["correct"])) for q in questions_of(items, qtype)
        ]
        points = []
        for step in range(101):
            threshold = step / 100
            kept = [ok for confidence, ok in answers if confidence >= threshold]
            if kept:
                points.append(
                    {
                        "threshold": threshold,
                        "coverage": len(kept) / len(answers),
                        "accuracy": sum(kept) / len(kept),
                        "n": len(kept),
                    }
                )
        curves[qtype] = {"points": points, "kit": kit[qtype]}
    return curves


def confusion(items: Sequence[Record], recipes: Sequence[Record]) -> Record:
    """Return gold-by-predicted matrices for every choice and noul question."""
    specs = {q["id"]: q for recipe in recipes for q in recipe["questions"]}
    matrices: Record = {}
    for qid, spec in specs.items():
        if spec["type"] == "noul":
            labels: list[Any] = [True, False]
            names = ["yes", "no"]
        else:
            labels = [option["label"] for option in spec["options"]]
            names = [
                str(option["label"]) if spec["type"] == "choice" else option["text"]
                for option in spec["options"]
            ]
        index = {json.dumps(label): i for i, label in enumerate(labels)}
        matrix = [[0] * len(labels) for _ in labels]
        for item in items:
            question = item["questions"].get(qid)
            if question is not None:
                matrix[index[json.dumps(question["gold"])]][
                    index[json.dumps(question["predicted"])]
                ] += 1
        matrices[qid] = {
            "type": spec["type"],
            "labels": names,
            "matrix": matrix,
            "rows": "gold",
            "columns": "predicted",
        }
    return matrices


def score_spread(items: Sequence[Record], recipes: Sequence[Record]) -> Record:
    """Return each score question's expected score per item and mean per gold level."""
    spread: Record = {}
    for recipe in recipes:
        for spec in recipe["questions"]:
            if spec["type"] != "score":
                continue
            levels = [option["text"] for option in spec["options"]]
            points = [
                {
                    "id": item["id"],
                    "split": item["split"],
                    "gold": q["gold"],
                    "expected": q["signal"],
                    "correct": q["correct"],
                }
                for item in items
                if (q := item["questions"].get(spec["id"])) is not None
            ]
            means = []
            for level, label in enumerate(levels):
                values = [p["expected"] for p in points if p["gold"] == level]
                means.append(
                    {
                        "level": level,
                        "label": label,
                        "n": len(values),
                        "mean_expected": sum(values) / len(values) if values else None,
                    }
                )
            spread[spec["id"]] = {
                "levels": levels,
                "points": points,
                "means": means,
                "legend": spec.get("legend"),
            }
    return spread
