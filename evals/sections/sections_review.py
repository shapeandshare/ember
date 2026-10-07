"""Report sections 11 to 17, from error analysis to the appendix.

See ``evals.document`` for the section order.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from typing import Any

from ..charts import charts
from ..render.blocks import (
    Block,
    Bullets,
    Card,
    Cards,
    Code,
    Definitions,
    Figure,
    Para,
    References,
    Table,
    cell,
    code,
    mark,
    num,
)
from ..render.markup import figure_id
from ..render.tone import Tone
from .sections_front import Built, Report, recipe_title

TONES = {
    "acted on a wrong answer": Tone.BAD,
    "acted, flagged for verification": Tone.WARN,
}


def _signal(miss: Mapping[str, Any]) -> str:
    if miss["type"] == "choice":
        return f"confidence {miss['signal']:.2f} ({miss['band']} band)"
    if miss["type"] == "noul":
        return f"P(true) {miss['signal']:.2f} ({miss['band']})"
    return f"expected {miss['signal']:.2f}, {miss['abs_error']:.2f} levels from gold"


def _answer_figure(report: Report, miss: Mapping[str, Any]) -> Figure:
    ident = figure_id(f"miss-{miss['id']}-{miss['question']}")
    title = f"ember's answer for {miss['id']}, {miss['question']}"
    if miss["type"] == "noul":
        return Figure(
            ident,
            lambda s: charts.track(
                f"fig-{ident}",
                title,
                "P(true) placed on the no, unsure, and yes zones.",
                miss["signal"],
                bool(miss["gold"]),
                standalone=s,
            ),
            "",
            f"P(true) for {miss['id']}",
            numbered=False,
        )
    if miss["type"] == "choice":
        labels = list(miss["probabilities"])
        values = [miss["probabilities"][k] for k in labels]
    else:
        labels = report["score_spread"][miss["question"]]["levels"]
        values = list(miss["probabilities"])
    gold = miss["gold"] if miss["type"] == "choice" else labels[miss["gold"]]
    chosen = (
        miss["predicted"] if miss["type"] == "choice" else labels[miss["predicted"]]
    )
    rows = [
        (
            label,
            value,
            "gold" if label == gold else "chosen" if label == chosen else None,
        )
        for label, value in zip(labels, values, strict=True)
    ]
    return Figure(
        ident,
        lambda s: charts.distribution(
            f"fig-{ident}",
            title,
            "Probability ember gave each option.",
            rows,
            standalone=s,
        ),
        "",
        f"ember's probabilities for {miss['id']}",
        numbered=False,
    )


def _miss_card(report: Report, miss: Mapping[str, Any]) -> Card:
    state = miss["state"]
    body: list[Block] = []
    if state is not None:
        if isinstance(state, str):
            body.append(Code(state, "text"))
        else:
            body.append(Code(json.dumps(state, indent=2), "json"))
    body.append(_answer_figure(report, miss))
    return Card(
        title=f"{miss['id']}: {miss['question']}",
        tag=f"{recipe_title(report, miss['category'])} · {miss['split']}",
        tone=TONES.get(miss["kit_outcome"], Tone.INFO),
        facts=(
            ("Gold", cell(f"{miss.get('gold_text', miss['gold'])} ({miss['gold']})")),
            (
                "ember",
                cell(
                    f"{miss.get('predicted_text', miss['predicted'])} "
                    f"({miss['predicted']})"
                ),
            ),
            ("Signal", cell(_signal(miss))),
            ("Kit outcome", cell(miss["kit_outcome"])),
            ("Why this gold label", cell(miss.get("rationale") or "not recorded")),
        ),
        body=tuple(body),
    )


def errors(report: Report) -> Built:
    """Build the review queue: every miss with its evidence."""
    misses = report["misses"]
    counts = Counter(m["kit_outcome"] for m in misses)
    blocks: list[Block] = [
        Para(
            f"The run has {len(misses)} misses. Each card shows the evidence ember "
            "saw, the gold label and its rationale, ember's full answer, and what "
            "an agent following the kit would have done with it. Reviewers can use "
            "this section as the label-review queue."
        ),
        Table(
            ("What the kit does with the miss", "Misses"),
            tuple((cell(k), num(v)) for k, v in counts.most_common()),
        ),
        Cards(tuple(_miss_card(report, m) for m in misses)),
    ]
    return ("errors", "Error analysis", blocks)


def latency(report: Report) -> Built:
    """Build the latency histogram and per-recipe means."""
    stats = report["latency"]
    values = stats["values"]
    markers = [("p50", stats.get("p50", 0.0)), ("p95", stats.get("p95", 0.0))]
    blocks: list[Block] = [
        Figure(
            "latency",
            lambda s: charts.histogram(
                "fig-latency",
                "Latency per request",
                "Histogram of request latency in ms.",
                values,
                markers=markers,
                unit="ms",
                standalone=s,
            ),
            "Wall-clock time per request, measured by the runner, including HTTP.",
            "Histogram of request latency",
        ),
        Table(
            ("Recipe", "Mean latency"),
            tuple(
                (cell(recipe_title(report, cat)), num(f"{ms:.0f} ms"))
                for cat, ms in stats["by_category"].items()
            ),
        ),
        Para(
            f"Mean {stats.get('mean', 0):.0f} ms, p50 {stats.get('p50', 0):.0f} ms, "
            f"p95 {stats.get('p95', 0):.0f} ms, max {stats.get('max', 0):.0f} ms on "
            f"the host in the System under test section."
        ),
    ]
    return ("latency", "Latency", blocks)


def limitations(report: Report) -> Built:
    """Build the threats to validity."""
    return (
        "limitations",
        "Limitations",
        [Bullets(tuple(report["text"]["limitations"]))],
    )


def reproducibility(report: Report) -> Built:
    """Build the commands and pins needed to reproduce the run."""
    meta = report["meta"]
    spec, host = meta["model_spec"], meta["host"]
    pins = [
        ("Commit", code(meta["git_hash"])),
        ("Dataset SHA-256", code(meta["dataset"]["sha256"])),
        ("Model revision", code(spec.get("revision", "not recorded"))),
        ("Results file", code(meta["results_file"])),
        ("Trace file", code(meta["trace_file"])),
        ("Bootstrap", cell("1,000 resamples, seed 0, percentile interval")),
        *(
            (f"Package {name}", code(version))
            for name, version in host.get("packages", {}).items()
        ),
    ]
    blocks: list[Block] = [
        Para(
            "Run these from a clone of the repository on Apple Silicon. Identical "
            "requests to the same server return identical answers, so a re-run on "
            "the pins below should reproduce these numbers."
        ),
        Code("\n".join(report["text"]["reproduce"]), "bash"),
        Table(("Pin", "Value"), tuple((cell(k), v) for k, v in pins)),
    ]
    return ("reproducibility", "Reproducibility", blocks)


def glossary(report: Report) -> Built:
    """Build the glossary."""
    items = tuple((term, meaning) for term, meaning in report["text"]["glossary"])
    return ("glossary", "Glossary", [Definitions(items)])


def references(report: Report) -> Built:
    """Build the numbered bibliography."""
    refs = tuple((r["key"], r["text"], r["url"]) for r in report["text"]["references"])
    return ("references", "References", [References(refs)])


def appendix(report: Report) -> Built:
    """Build the full item table with filters."""
    rows, data = [], []
    for item in report["items"]:
        lines = []
        for qid, q in item["questions"].items():
            status = "ok" if q["correct"] else "miss"
            lines.append(
                f"{qid}: {q['gold']} -> {q['predicted']} ({status}, {q['signal']:.2f})"
            )
        rows.append(
            (
                code(item["id"]),
                cell(recipe_title(report, item["category"])),
                cell(item["split"]),
                mark(bool(item["correct"])),
                cell("\n".join(lines)),
            )
        )
        data.append(
            {
                "recipe": item["category"],
                "split": item["split"],
                "result": "correct" if item["correct"] else "incorrect",
            }
        )
    categories = tuple(dict.fromkeys(i["category"] for i in report["items"]))
    table = Table(
        ("Item", "Recipe", "Split", "Result", "Questions: gold -> ember (signal)"),
        tuple(rows),
        anchor="items",
        row_data=tuple(data),
        filters=(
            ("recipe", "Recipe", categories),
            ("split", "Split", ("dev", "test")),
            ("result", "Result", ("correct", "incorrect")),
        ),
        collapse=f"All {len(rows)} items",
    )
    blocks: list[Block] = [
        Para(
            "Every scored item with each question's gold label, ember's answer, and "
            "its signal (confidence for `choice`, P(true) for `noul`, expected value "
            "for `score`). The raw run data ships next to this report in `data/`."
        ),
        table,
    ]
    return ("appendix", "Appendix: every item", blocks)
