"""Report sections 6 to 10, from results to confusion matrices.

See ``evals.document`` for the section order.
"""

from __future__ import annotations

import json
from typing import Any

from ..charts import charts, charts_calibration
from ..render.blocks import (
    Block,
    Definitions,
    Figure,
    Heading,
    Para,
    Table,
    cell,
    code,
    dec,
    interval,
    num,
    pct,
)
from .sections_front import Built, Report, recipe_title
from .sections_phase0 import phase0_blocks

TYPES = ("choice", "noul", "score")


def evidence(state: Any) -> str:
    """Return the most telling line of an item's state."""
    if isinstance(state, str):
        return state
    if isinstance(state, dict):
        for key in ("diff_summary", "output", "error", "task"):
            if key in state:
                return str(state[key])
    return json.dumps(state)


def results(report: Report) -> Built:
    """Build accuracy tables and charts by type, question, recipe, and split."""
    summary = report["summary"]
    type_rows, bars = [], []
    for qtype in TYPES:
        part = summary[qtype]
        if not part:
            continue
        type_rows.append(
            (
                code(qtype),
                num(part["n"]),
                num(pct(part["accuracy"])),
                cell(interval(part["accuracy_ci"])),
                num(dec(part.get("macro_f1"))),
                num(dec(part.get("ece"))),
                num(dec(part.get("brier"))),
                num(dec(part.get("rps"))),
                num(dec(part.get("mae"))),
            )
        )
        low, high = part["accuracy_ci"]
        bars.append(
            {
                "label": qtype,
                "value": part["accuracy"],
                "low": low,
                "high": high,
                "note": f"n={part['n']}",
            }
        )
    blocks: list[Block] = [
        Heading("By question type", "by-type"),
        Table(
            (
                "Type",
                "N",
                "Accuracy",
                "95% CI",
                "Macro-F1",
                "ECE",
                "Brier",
                "RPS",
                "MAE",
            ),
            tuple(type_rows),
            caption="Lower is better for ECE, Brier, RPS, and MAE.",
        ),
        Figure(
            "accuracy-by-type",
            lambda s: charts.hbars(
                "fig-accuracy-by-type",
                "Accuracy by type",
                "Accuracy per question type with 95% intervals.",
                bars,
                standalone=s,
            ),
            "Accuracy by question type, with 95% bootstrap intervals.",
            "Bar chart of accuracy by question type",
        ),
    ]
    if summary["score"]:
        score = summary["score"]
        blocks.append(
            Para(
                "A `score` answer counts as correct when its expected value rounds to "
                f"the gold level. {pct(score['within_one'])} land within one level, "
                f"and the mean absolute error is {score['mae']:.2f} levels."
            )
        )
    scales = report["text"].get("scales") or []
    if scales:
        blocks += [
            Heading("Scales", "scales"),
            Para(
                "Every `score` scale runs from least to most of its quantity; index 0 "
                "is always the least. The dangerous end is the pole the asymmetric "
                "metrics watch."
            ),
            Definitions(
                tuple(
                    (
                        f"`{scale['question']}`",
                        f"{scale['legend']} (dangerous end: {scale['dangerous_end']})",
                    )
                    for scale in scales
                )
            ),
        ]
    question_rows, question_bars = [], []
    for qid, q in summary["questions"].items():
        question_rows.append(
            (
                code(qid),
                cell(recipe_title(report, q["category"])),
                code(q["type"]),
                num(q["n"]),
                num(pct(q["accuracy"])),
                num(dec(q.get("brier", q.get("rps")))),
                num(dec(q.get("mae"))),
            )
        )
        question_bars.append(
            {"label": qid, "value": q["accuracy"], "note": f"n={q['n']}"}
        )
    recipe_rows = [
        (
            cell(recipe_title(report, cat)),
            num(c["items"]),
            num(pct(c["item_accuracy"])),
            num(pct(c["accuracy"])),
        )
        for cat, c in summary["categories"].items()
    ]
    split_rows = [
        (
            code(name),
            num(s["items"]),
            num(s["questions"]),
            num(pct(s["accuracy"])),
            cell(interval(s["accuracy_ci"])),
            num(pct(s["item_accuracy"])),
            *(num(pct(s["by_type"].get(t))) for t in TYPES),
        )
        for name, s in report["splits"].items()
    ]
    blocks += [
        Heading("By question", "by-question"),
        Table(
            ("Question", "Recipe", "Type", "N", "Accuracy", "Brier or RPS", "MAE"),
            tuple(question_rows),
        ),
        Figure(
            "accuracy-by-question",
            lambda s: charts.hbars(
                "fig-accuracy-by-question",
                "Accuracy by question",
                "Accuracy for each of the nine questions.",
                question_bars,
                standalone=s,
            ),
            "Accuracy for each question. `score` questions count exact levels "
            "only; read them with MAE.",
            "Bar chart of accuracy by question",
        ),
        Heading("By recipe", "by-recipe"),
        Table(
            ("Recipe", "Items", "Items fully correct", "Question accuracy"),
            tuple(recipe_rows),
        ),
        Heading("dev and test", "splits"),
        Table(
            (
                "Split",
                "Items",
                "Questions",
                "Accuracy",
                "95% CI",
                "Items fully correct",
                "choice",
                "noul",
                "score",
            ),
            tuple(split_rows),
        ),
    ]
    blocks += phase0_blocks(report)
    return ("results", "Results", blocks)


def calibration(report: Report) -> Built:
    """Build reliability diagrams and the calibration summary."""
    summary = report["summary"]
    blocks: list[Block] = [Para(p) for p in report["text"]["reliability"]]
    figures, rows = [], []
    for qtype in ("choice", "noul"):
        part = summary[qtype]
        if not part:
            continue
        bins = part["reliability"]
        figures.append(
            Figure(
                f"reliability-{qtype}",
                lambda s, bins=bins, part=part, qtype=qtype: (
                    charts_calibration.reliability(
                        f"fig-reliability-{qtype}",
                        f"Reliability of {qtype} answers",
                        "Accuracy bars per confidence bin against the diagonal "
                        "of perfect calibration.",
                        bins,
                        ece=part["ece"],
                        mce=part["mce"],
                        standalone=s,
                    )
                ),
                f"Reliability of `{qtype}` answers ({part['n']} questions). Coral "
                "lines mark each bin's mean confidence; shading below a line marks "
                "over-confidence.",
                f"Reliability diagram for {qtype} answers",
            )
        )
        total = sum(b["n"] for b in bins)
        mean = sum(b["n"] * b["confidence"] for b in bins) / total if total else 0.0
        gap = part["accuracy"] - mean
        label = (
            "under-confident"
            if gap > 0.05
            else "over-confident"
            if gap < -0.05
            else "close"
        )
        rows.append(
            (
                code(qtype),
                num(part["n"]),
                num(dec(mean)),
                num(pct(part["accuracy"])),
                cell(f"{gap:+.3f} ({label})"),
                num(dec(part["ece"])),
                num(dec(part["mce"])),
                num(dec(part["brier"])),
            )
        )
    blocks += [
        *figures,
        Table(
            (
                "Type",
                "N",
                "Mean confidence",
                "Accuracy",
                "Accuracy minus confidence",
                "ECE",
                "MCE",
                "Brier",
            ),
            tuple(rows),
        ),
    ]
    return ("calibration", "Calibration", blocks)
