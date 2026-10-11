"""Results-section blocks added by specs/004 Phase 0.

The capability panel, dangerous recall for risk recipes, variant consistency,
accuracy by source kind, difficulty tiers, and accuracy by state length.
"""

from __future__ import annotations

from ..charts import charts_tokens
from ..render.blocks import Block, Figure, Heading, Para, Table, cell, code, num, pct
from .sections_front import Report


def _capability_blocks(summary: Report) -> list[Block]:
    capability = summary.get("capability")
    if not capability:
        return []
    rows = tuple(
        (
            code(category),
            num(block["items"]),
            num(pct(block["item_accuracy"])),
            num(pct(block["accuracy"])),
        )
        for category, block in capability["categories"].items()
    )
    return [
        Heading("Capability panel", "capability"),
        Para(
            "Vision recipes are smoke checks of the media path, not a benchmark. They "
            "sit outside the headline so synthetic swatches cannot inflate it."
        ),
        Table(("Recipe", "Items", "Items fully correct", "Question accuracy"), rows),
    ]


def _risk_blocks(summary: Report) -> list[Block]:
    risk = summary.get("risk") or {}
    if not risk:
        return []
    rows = []
    for category, block in risk.items():
        recall = block["dangerous_recall_at_threshold"]
        rows.append(
            (
                code(category),
                num(pct(recall) if recall is not None else "—"),
                num(block["missed_dangers"]),
                num(f"{block['bar']:.2f}"),
                cell("met" if block["met"] else "**not met**"),
            )
        )
    return [
        Heading("Dangerous recall", "dangerous-recall"),
        Para(
            "For risk recipes a missed danger costs far more than a false alarm. "
            "Recall is measured at the kit's acting threshold: among unsafe items the "
            "agent would act on, the share called unsafe. Missed dangers are confident "
            "safe verdicts on unsafe items."
        ),
        Table(
            (
                "Recipe",
                "Dangerous recall at threshold",
                "Missed dangers",
                "Bar",
                "Status",
            ),
            tuple(rows),
        ),
    ]


def _consistency_blocks(summary: Report) -> list[Block]:
    consistency = summary.get("consistency") or {}
    if not consistency:
        return []
    rows = tuple(
        (code(category), num(block["groups"]), num(pct(block["agreement"])))
        for category, block in consistency.items()
    )
    return [
        Heading("Consistency", "consistency"),
        Para(
            "A variant group is an item and its paraphrase or format variants; "
            "agreement is the share of groups whose members all received the same "
            "answer."
        ),
        Table(("Recipe", "Variant groups", "Agreement"), rows),
    ]


def _by_source_blocks(summary: Report) -> list[Block]:
    by_source = summary.get("by_source_kind") or {}
    if not by_source:
        return []
    rows = tuple(
        (code(category), code(kind), num(block["items"]), num(pct(block["accuracy"])))
        for category, kinds in by_source.items()
        for kind, block in kinds.items()
    )
    return [
        Heading("By source", "by-source"),
        Para(
            "Accuracy per source kind, so imported data and authored items are never "
            "averaged away."
        ),
        Table(("Recipe", "Source kind", "Items", "Question accuracy"), rows),
    ]


def _tiers_blocks(summary: Report) -> list[Block]:
    tiers = summary.get("tiers")
    if not tiers:
        return []
    overall = summary["overall"]
    non_easy = tiers["non_easy"]
    intro = Para(
        f"{tiers['easy_items']} items are tagged `easy` (every row on this dataset "
        "version got them fully right). Growth in easy items cannot inflate the "
        "headline while the non-easy figure sits beside it."
    )
    if not non_easy["items"]:
        return [
            Heading("Difficulty tiers", "tiers"),
            intro,
            Para(
                "Every scored item is tagged `easy`, so the non-easy subset is empty "
                "and no separate accuracy is shown for it."
            ),
        ]
    return [
        Heading("Difficulty tiers", "tiers"),
        intro,
        Table(
            ("Subset", "Items", "Questions", "Accuracy"),
            (
                (
                    cell("All items"),
                    num(overall["items"]),
                    num(overall["questions"]),
                    num(pct(overall["accuracy"])),
                ),
                (
                    cell("Non-easy"),
                    num(non_easy["items"]),
                    num(non_easy["questions"]),
                    num(pct(non_easy["accuracy"])),
                ),
            ),
        ),
    ]


def _tokens_blocks(report: Report) -> list[Block]:
    tokens = report["summary"].get("tokens")
    if not tokens:
        return [
            Heading("State length", "tokens"),
            Para(
                "The token split is unavailable for this run: its trace predates the "
                "server's `usage` split, and the split is never inferred."
            ),
        ]
    return [
        Heading("State length", "tokens"),
        Figure(
            "tokens",
            lambda s, bins=tokens["state_bins"]: charts_tokens.tokens_chart(
                "fig-tokens",
                "Accuracy and Brier by state length",
                "Bars of accuracy and a line of Brier score per state-token bin.",
                bins,
                standalone=s,
            ),
            "Accuracy and Brier against state tokens. Median state "
            f"{tokens['median_state']:.0f} tokens, maximum {tokens['max_state']}.",
            "Bar chart of accuracy by state-token bin with a Brier line",
        ),
    ]


def phase0_blocks(report: Report) -> list[Block]:
    """Build the capability, risk, consistency, by-source, tiers, and length blocks."""
    summary = report["summary"]
    blocks: list[Block] = []
    blocks += _capability_blocks(summary)
    blocks += _risk_blocks(summary)
    blocks += _consistency_blocks(summary)
    blocks += _by_source_blocks(summary)
    blocks += _tiers_blocks(summary)
    blocks += _tokens_blocks(report)
    return blocks
