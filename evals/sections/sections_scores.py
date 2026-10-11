"""Report sections 9 and 10: ordinal answers and confusion matrices.

Split out of ``evals/sections/sections_results.py`` (Article X §10.3). See
``evals.document`` for the section order.
"""

from __future__ import annotations

from ..charts import charts_calibration
from ..render.blocks import Block, Figure, Gallery, Para, Table, cell, dec, num
from .sections_front import Built, Report


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
        if spread.get("legend"):
            blocks.append(Para(f"Scale: {spread['legend']}"))
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
