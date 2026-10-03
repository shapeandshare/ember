"""Report sections 1 to 5: summary, context, system, design, and metrics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import charts
from .blocks import (
    Block,
    Bullets,
    Callout,
    Card,
    Cards,
    Cell,
    Definitions,
    Figure,
    Formula,
    Heading,
    Kpi,
    Kpis,
    Para,
    Table,
    cell,
    code,
    interval,
    num,
    pct,
)

Report = Mapping[str, Any]
Built = tuple[str, str, list[Block]]


def slug(value: str) -> str:
    """Return an anchor-safe slug."""
    kept = "".join(ch if ch.isalnum() else "-" for ch in value.lower())
    return "-".join(part for part in kept.split("-") if part)


def recipe_title(report: Report, category: str) -> str:
    """Return a recipe's display title."""
    for recipe in report["recipes"]:
        if recipe["category"] == category:
            return str(recipe.get("title", category))
    return category


def summary(report: Report) -> Built:
    """Build the headline numbers and the key findings."""
    overall = report["summary"]["overall"]
    acting = [b for b in report["bands"]["choice"] if b["band"] == "trust"]
    acting += [b for b in report["bands"]["noul"] if b["band"] in ("yes", "no")]
    acted = sum(b["n"] for b in acting)
    right = sum(b["correct"] for b in acting)
    wrong = sum(p["wrong_action"] for p in report["policies"])
    decisions = sum(p["n"] for p in report["policies"])
    latency = report["latency"]
    kpis = Kpis(
        (
            Kpi(
                "Question accuracy",
                pct(overall["accuracy"]),
                f"95% CI {interval(overall['accuracy_ci'])}, "
                f"{overall['questions']} questions",
            ),
            Kpi(
                "Items fully correct",
                pct(overall["item_accuracy"]),
                f"{overall['items']} items",
            ),
            Kpi(
                "Right when the kit acts",
                f"{right} of {acted}",
                "answers past the act-on-it thresholds",
                "good" if right == acted else "warn",
            ),
            Kpi(
                "Wrong actions, default policy",
                f"{wrong} of {decisions}",
                "policy decisions replayed",
                "warn" if wrong else "good",
            ),
            Kpi("Misses to review", str(len(report["misses"])), "see Error analysis"),
            Kpi(
                "Latency per request",
                f"{latency.get('mean', 0):.0f} ms",
                f"p95 {latency.get('p95', 0):.0f} ms",
            ),
        )
    )
    blocks: list[Block] = [kpis, Heading("Key findings", "key-findings")]
    blocks += [Callout(f["tone"], f["title"], f["text"]) for f in report["findings"]]
    return ("summary", "Summary", blocks)


def context(report: Report) -> Built:
    """Build what ember is and why calibration matters."""
    text = report["text"]
    blocks: list[Block] = [Para(p) for p in text["context"]]
    blocks.append(
        Table(
            ("Type", "Asks", "Returns", "Counts as correct when"),
            tuple(
                (
                    code(q["type"]),
                    cell(q["asks"]),
                    cell(q["returns"]),
                    cell(q["correct"]),
                )
                for q in text["question_types"]
            ),
        )
    )
    return ("context", "Context", blocks)


def system(report: Report) -> Built:
    """Build the system under test: architecture and exact environment."""
    meta, text = report["meta"], report["text"]
    spec, engine, host = meta["model_spec"], meta["engine"], meta["host"]
    nodes, edges = text["architecture"]["nodes"], text["architecture"]["edges"]
    packages = ", ".join(f"{k} {v}" for k, v in host.get("packages", {}).items())
    software = f"Python {host.get('python', '?')}" + (
        f", {packages}" if packages else ""
    )
    window = engine.get("max_length")
    dataset = meta["dataset"]
    facts = [
        (
            "Model",
            cell(
                f"{spec.get('repo', meta['model'])}, "
                f"{spec.get('params', '?')} parameters"
            ),
        ),
        ("Pinned revision", code(spec.get("revision", "not recorded"))),
        (
            "Device and precision",
            cell(f"{engine.get('device', '?')}, {engine.get('dtype', '?')}"),
        ),
        ("Context window", cell(f"{window:,} tokens" if window else "not recorded")),
        (
            "Host",
            cell(f"{host.get('cpu', 'not recorded')}, {host.get('platform', '')}"),
        ),
        ("Software", cell(software)),
        ("Server", code(meta["server"])),
        ("Commit", code(meta["git_hash"])),
        ("Run at", cell(meta["run_at"])),
        ("Report generated", cell(meta["generated_at"])),
        ("Dataset", code(dataset["name"])),
        ("Dataset SHA-256", code(dataset["sha256"])),
        (
            "Dataset unchanged since the run",
            Cell("yes", "good") if dataset["matches"] else Cell("no", "bad"),
        ),
        ("Request errors", num(meta["n_errors"])),
    ]
    blocks: list[Block] = [Para(p) for p in text["system"]]
    blocks.append(
        Figure(
            "architecture",
            lambda s: charts.architecture(
                "fig-architecture",
                "ember call path",
                "Boxes for the agent, ember-mcp, the model server, and Clef-Flash, "
                "joined left to right; the agent eval runner drives the agent and the "
                "benchmark runner calls the model server directly.",
                nodes,
                edges,
                standalone=s,
            ),
            "The call path of an agent's `advise` call. The dashed routes are the "
            "two runners: the agent eval drives a coding agent, and the benchmark "
            "posts straight to the model server.",
            "Architecture diagram of the ember call path",
            text=text.get("architecture_text", ""),
        )
    )
    blocks.append(
        Table(
            ("Fact", "Value"),
            tuple((cell(k), v) for k, v in facts),
            anchor="environment",
        )
    )
    return ("system", "System under test", blocks)


def _recipe_card(recipe: Mapping[str, Any]) -> Card:
    rows = []
    for question in recipe["questions"]:
        options = "\n".join(f"{o['label']}: {o['text']}" for o in question["options"])
        rows.append(
            (
                code(question["id"]),
                code(question["type"]),
                cell(question["instructions"]),
                cell(options or "yes or no"),
            )
        )
    return Card(
        title=str(recipe.get("title", recipe["category"])),
        tag=recipe["category"],
        tone="info",
        facts=(
            ("When", cell(recipe.get("when", ""))),
            ("State", cell(recipe.get("state", ""))),
            ("Decides", cell(recipe.get("decides", ""))),
        ),
        body=(Table(("Question", "Type", "Asks", "Options"), tuple(rows)),),
    )


def design(report: Report) -> Built:
    """Build the dataset, its balance, the recipes, and the labelling protocol."""
    text, composition = report["text"], report["composition"]
    rows = [
        {"label": r["title"], "values": {"dev": r["dev"], "test": r["test"]}}
        for r in composition["recipes"]
    ]
    keys = (
        ("dev", "dev (tuning)", "c-ter", "c-text"),
        ("test", "test (reporting)", "c-pri", "c-on-pri"),
    )
    blocks: list[Block] = [Para(p) for p in text["dataset"]]
    blocks.append(
        Figure(
            "composition",
            lambda s: charts.stacked(
                "fig-composition",
                "Items per recipe and split",
                "Stacked bars of dev and test items for each recipe.",
                rows,
                keys,
                standalone=s,
            ),
            "Items per recipe, split into `dev` and `test`.",
            "Bar chart of items per recipe by split",
        )
    )
    balance = []
    for qid, entry in composition["labels"].items():
        for index, label in enumerate(entry["labels"]):
            balance.append(
                (
                    code(qid) if index == 0 else cell(""),
                    code(label["label"]),
                    cell(label["text"]),
                    num(label["dev"]),
                    num(label["test"]),
                )
            )
    blocks += [
        Heading("Label balance", "label-balance"),
        Table(("Question", "Gold label", "Meaning", "dev", "test"), tuple(balance)),
        Heading("Recipes", "recipes"),
        Para(
            "Each recipe asks the same fixed question set for every item, because "
            "ember weighs the questions in one call jointly."
        ),
        Cards(tuple(_recipe_card(r) for r in report["recipes"])),
        Heading("Labelling protocol", "protocol"),
        Bullets(tuple(text["protocol"])),
        Heading("Dataset card", "datasheet"),
        Definitions(tuple((q, a) for q, a in text["datasheet"])),
    ]
    return ("design", "Benchmark design", blocks)


def metrics(report: Report) -> Built:
    """Build metric definitions with formulas and sources."""
    blocks: list[Block] = [
        Para(
            "`evals/metrics.py` computes every metric from the run's trace; the "
            "definitions follow the cited sources."
        )
    ]
    for metric in report["text"]["metrics"]:
        applies = "every question" if metric["applies"] == "all" else metric["applies"]
        blocks += [
            Heading(metric["name"], f"metric-{slug(metric['name'])}"),
            Para(metric["definition"]),
            Formula(metric["tex"], metric["text"]),
            Para(f"**Applies to:** {applies}."),
        ]
    return ("metrics", "Metrics", blocks)
