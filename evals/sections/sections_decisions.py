"""Report section 8: the agent kit's decision rules replayed on every item.

Split out of ``evals/sections/sections_results.py`` (Article X §10.3). See
``evals.document`` for the section order.
"""

from __future__ import annotations

from ..charts import charts, charts_calibration
from ..render.blocks import (
    Block,
    Cell,
    Figure,
    Heading,
    Para,
    Table,
    cell,
    code,
    num,
    pct,
)
from .sections_front import Built, Report
from .sections_results import evidence


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
        if coverage.get(qtype) and coverage[qtype]["points"]
    ]
    blocks += [Heading("Coverage and accuracy", "coverage"), *figures]
    blocks += _policy_blocks(report)
    return ("decisions", "Decisions under the agent kit", blocks)
