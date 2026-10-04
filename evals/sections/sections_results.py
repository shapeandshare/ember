"""Report sections 6 to 10, from results to confusion matrices.

See ``evals.document`` for the section order.
"""

from __future__ import annotations

import json
from typing import Any

from ..charts import charts, charts_calibration
from ..render.blocks import (
    Block,
    Cell,
    Figure,
    Gallery,
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


def _policy_blocks(report: Report) -> list[Block]:
    items = {item["id"]: item for item in report["items"]}
    blocks: list[Block] = [Heading("Default project policy", "policy")]
    blocks += [Para(p) for p in report["text"]["policies"]]
    names = {
        "right": "Right action",
        "extra_step": "Extra step",
        "wrong_action": "Wrong action",
    }
    for policy in report["policies"]:
        meaning = {
            "right": "did what the gold label calls for",
            "extra_step": policy["extra_label"],
            "wrong_action": policy["wrong_label"],
        }
        outcomes = tuple(
            (
                Cell(
                    names[k],
                    "good"
                    if k == "right"
                    else "bad"
                    if k == "wrong_action"
                    else "text",
                ),
                num(policy[k]),
                cell(meaning[k]),
            )
            for k in ("right", "extra_step", "wrong_action")
        )
        blocks += [
            Heading(policy["title"], f"policy-{policy['key']}"),
            Para(f"**Rule:** {policy['rule']} Replayed on {policy['n']} items."),
            Table(("Outcome", "Items", "Meaning"), outcomes),
        ]
        if policy["cases"]:
            cases = tuple(
                (
                    code(case["id"]),
                    cell(meaning[case["outcome"]]),
                    cell(evidence(items[case["id"]]["state"])),
                    cell("\n".join(f"{k} {v:.2f}" for k, v in case["signals"].items())),
                )
                for case in policy["cases"]
            )
            blocks.append(
                Table(("Item", "Outcome", "Evidence", "ember's signals"), cases)
            )
    return blocks


def decisions(report: Report) -> Built:
    """Build confidence bands, coverage curves, and policy replays."""
    bands, coverage = report["bands"], report["coverage"]
    blocks: list[Block] = [
        Heading("Confidence bands", "bands"),
        Para(
            "The agent kit maps every answer to an action by its confidence. These "
            "tables replay that mapping on every answer in the run."
        ),
    ]
    for qtype, rows in bands.items():
        blocks.append(
            Table(
                (
                    f"{qtype} band",
                    "Rule",
                    "Agent action",
                    "Answers",
                    "Share",
                    "Correct",
                    "Accuracy",
                ),
                tuple(
                    (
                        code(b["band"]),
                        cell(b["rule"]),
                        cell(b["action"]),
                        num(b["n"]),
                        num(pct(b["share"])),
                        num(b["correct"]),
                        num(pct(b["accuracy"])),
                    )
                    for b in rows
                ),
            )
        )
    share = {
        qtype: {b["band"]: b["share"] for b in rows} for qtype, rows in bands.items()
    }
    stack = [
        {
            "label": "choice",
            "values": {
                "act": share["choice"].get("trust", 0),
                "verify": share["choice"].get("verify", 0),
                "defer": share["choice"].get("defer", 0),
            },
        },
        {
            "label": "noul",
            "values": {
                "act": share["noul"].get("yes", 0) + share["noul"].get("no", 0),
                "defer": share["noul"].get("unsure", 0),
            },
        },
    ]
    keys = (
        ("act", "acts on it", "c-pri", "c-on-pri"),
        ("verify", "acts and verifies", "c-ter", "c-text"),
        ("defer", "defers or asks", "c-sec", "c-text"),
    )
    blocks.append(
        Figure(
            "bands",
            lambda s: charts.stacked(
                "fig-bands",
                "What the kit does with each answer",
                "Share of answers in each action band.",
                stack,
                keys,
                standalone=s,
                percent=True,
            ),
            "Share of answers the kit acts on, acts on with verification, or defers.",
            "Stacked bar chart of answers by action band",
        )
    )
    figures = [
        Figure(
            f"coverage-{qtype}",
            lambda s, qtype=qtype: charts_calibration.coverage(
                f"fig-coverage-{qtype}",
                f"Coverage and accuracy, {qtype}",
                "Coverage and accuracy as the confidence threshold rises.",
                coverage[qtype]["points"],
                coverage[qtype]["kit"],
                standalone=s,
            ),
            f"`{qtype}`: coverage and accuracy as the threshold rises. Dashed lines "
            "mark the kit's thresholds.",
            f"Coverage and accuracy curves for {qtype} answers",
        )
        for qtype in ("choice", "noul")
        if coverage.get(qtype)
    ]
    blocks += [Heading("Coverage and accuracy", "coverage"), *figures]
    blocks += _policy_blocks(report)
    return ("decisions", "Decisions under the agent kit", blocks)


def ordinal(report: Report) -> Built:
    """Build strip plots of expected scores by gold level."""
    blocks: list[Block] = [
        Para(
            "A `score` question returns a distribution over ordered levels, and agents "
            "read its expected value. Each plot shows where that value lands for every "
            "gold level; a perfect advisor puts every dot on its dashed gold line."
        )
    ]
    for qid, spread in report["score_spread"].items():
        threshold = ("review line 2.0", 2.0) if qid == "risk" else None
        blocks.append(
            Figure(
                f"spread-{qid}",
                lambda s, qid=qid, spread=spread, threshold=threshold: (
                    charts_calibration.strip(
                        f"fig-spread-{qid}",
                        f"Expected {qid} score by gold level",
                        "Dots for each item's expected score, grouped by gold level.",
                        spread["levels"],
                        spread["points"],
                        spread["means"],
                        threshold=threshold,
                        standalone=s,
                    )
                ),
                f"Expected `{qid}` score by gold level."
                + (
                    " The orange line is the policy's review threshold."
                    if threshold
                    else ""
                ),
                f"Strip plot of expected {qid} scores by gold level",
            )
        )
        rows = []
        for mean in spread["means"]:
            members = [p for p in spread["points"] if p["gold"] == mean["level"]]
            within = sum(abs(p["expected"] - p["gold"]) <= 1 for p in members)
            exact = sum(bool(p["correct"]) for p in members)
            rows.append(
                (
                    cell(f"{mean['level']}: {mean['label']}"),
                    num(mean["n"]),
                    num(dec(mean["mean_expected"], 2)),
                    num(f"{exact} of {len(members)}"),
                    num(f"{within} of {len(members)}"),
                )
            )
        blocks.append(
            Table(
                (
                    "Gold level",
                    "Items",
                    "Mean expected",
                    "Exact level",
                    "Within one level",
                ),
                tuple(rows),
            )
        )
    return ("ordinal", "Ordinal answers", blocks)


def confusion(report: Report) -> Built:
    """Build one confusion heatmap per question."""
    figures = []
    for qid, entry in report["confusion"].items():
        figures.append(
            Figure(
                f"confusion-{qid}",
                lambda s, qid=qid, entry=entry: charts_calibration.heatmap(
                    f"fig-confusion-{qid}",
                    f"Confusion matrix for {qid}",
                    "Counts of answers by gold label and ember's answer.",
                    entry["labels"],
                    entry["matrix"],
                    standalone=s,
                ),
                f"`{qid}` ({entry['type']}).",
                f"Confusion matrix for {qid}",
            )
        )
    blocks: list[Block] = [
        Para(
            "Each matrix counts answers by gold label (rows) and ember's answer "
            "(columns). The outlined diagonal is agreement."
        ),
        Gallery(tuple(figures)),
    ]
    return ("confusion", "Confusion matrices", blocks)
