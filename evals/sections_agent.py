"""Report section for the agent-in-the-loop run (present when one is attached)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import charts, charts_agent
from .agent.report import short
from .blocks import (
    Block,
    Callout,
    Figure,
    Heading,
    Kpi,
    Kpis,
    Para,
    Table,
    cell,
    code,
    num,
    pct,
)
from .sections_front import Built

Report = Mapping[str, Any]


def _rate(entry: Mapping[str, Any] | None) -> str:
    return pct(entry["rate"]) if entry else "n/a"


def _ordered(agent: Report, rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Sort rows by the run's model order, then none, mcp, skill, full."""
    models, conditions = agent["config"]["models"], agent["config"]["conditions"]
    return sorted(
        rows, key=lambda r: (models.index(r["model"]), conditions.index(r["condition"]))
    )


def _groups(agent: Report) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {(g["model"], g["condition"]): g for g in agent["summary"]["groups"]}


def _kpis(agent: Report) -> Kpis:
    groups = _groups(agent)
    items = []
    for model in agent["config"]["models"]:
        full, none = groups.get((model, "full")), groups.get((model, "none"))
        if full:
            items.append(
                Kpi(
                    f"{short(model)}: gold action, full kit",
                    _rate(full["action"]),
                    f"{_rate(none['action']) if none else 'n/a'} without ember",
                )
            )
            items.append(
                Kpi(
                    f"{short(model)}: consults ember",
                    _rate(full["consult"]),
                    "decision sessions, full kit",
                )
            )
    summary = agent["summary"]
    overall = summary.get("overall") or {}
    if overall.get("accuracy") is not None:
        low, high = overall.get("accuracy_ci", [0.0, 1.0])
        items.insert(
            0,
            Kpi(
                "Overall gold-action accuracy",
                pct(overall["accuracy"]),
                f"95% CI [{low * 100:.1f}, {high * 100:.1f}] "
                f"over {summary['valid']} sessions",
                tone="good" if overall["accuracy"] >= 0.90 else "warn",
            ),
        )
    if overall.get("wrong_actions") is not None:
        items.append(
            Kpi(
                "Wrong actions, default policy",
                str(overall["wrong_actions"]),
                f"of {summary['valid']} sessions where kit signal was clear",
                tone="warn" if overall["wrong_actions"] else "good",
            )
        )
    items.append(
        Kpi(
            "Sessions",
            f"{summary['valid']} of {summary['runs']}",
            f"valid; ${agent['cost_total']:.2f} provider cost",
        )
    )
    return Kpis(tuple(items))


def _table(agent: Report) -> Table:
    rows = []
    for g in _ordered(agent, agent["summary"]["groups"]):
        rows.append(
            (
                code(short(g["model"])),
                code(g["condition"]),
                num(g["runs"]),
                num(_rate(g["action"])),
                num(_rate(g["consult"])),
                num(_rate(g["before_act"])),
                num(_rate(g["recipe_fidelity"])),
                num(_rate(g["evidence"])),
                num(_rate(g["followed"])),
                num(
                    f"{g['call_quality']:.2f}"
                    if g.get("call_quality") is not None
                    else "n/a"
                ),
                num(_rate(g.get("cq_batched"))),
                num(_rate(g.get("cq_verdict_free"))),
                num(_rate(g.get("cq_ids_correct"))),
                num(_rate(g["over_consult"])),
                num(f"{g['cost'] or 0:.4f}"),
                num(f"{g['seconds'] or 0:.0f}"),
            )
        )
    return Table(
        (
            "Model",
            "Condition",
            "Sessions",
            "Gold action",
            "Consults",
            "Before acting",
            "Kit questions",
            "Evidence",
            "Follows ember",
            "Call quality",
            "Batched ↑",
            "No verdict ↑",
            "Kit ids ↑",
            "Unneeded",
            "$ / session",
            "s / session",
        ),
        tuple(rows),
        caption="Call quality columns (consulted sessions only): Batched = all "
        "questions in one call; No verdict = state carried raw evidence not a "
        "conclusion; Kit ids = only recipe question ids used. Score = mean of the "
        "three. Unneeded: control sessions with an ember call.",
    )


def _pivot(agent: Report, key: str, conditions: list[str]) -> Table:
    models = agent["config"]["models"]
    columns = [(m, c) for m in models for c in conditions]
    cells: dict[tuple[str, str, str], Any] = {
        (r["recipe"], r["model"], r["condition"]): r[key]
        for r in agent["summary"]["recipes"]
    }
    recipes = sorted({r["recipe"] for r in agent["summary"]["recipes"]})
    rows = tuple(
        (code(recipe), *(num(_rate(cells.get((recipe, m, c)))) for m, c in columns))
        for recipe in recipes
    )
    return Table(("Recipe", *(f"{short(m)} {c}" for m, c in columns)), rows)


def agent_section(report: Report) -> Built:
    """Build the agent-in-the-loop section from ``report['agent']``."""
    agent = report["agent"]
    config, summary = agent["config"], agent["summary"]
    blocks: list[Block] = [Para(p) for p in agent["narrative"]]
    flow = agent["flow"]
    blocks.append(
        Figure(
            "agent-flow",
            lambda s: charts.architecture(
                "fig-agent-flow",
                "How one agent session is scored",
                "A scenario becomes a sandbox, opencode works in it and may consult "
                "ember, the judge scores the effects, and sessions roll up per model "
                "and condition.",
                flow["nodes"],
                flow["edges"],
                standalone=s,
            ),
            "How one session flows. The dashed call to ember exists only in the "
            "`mcp`, `skill`, and `full` conditions; the judge sees only the effects.",
            "Flow diagram of an agent-in-the-loop session",
            text=agent.get("flow_text", ""),
        )
    )
    blocks.append(_kpis(agent))
    blocks += [Callout(f["tone"], f["title"], f["text"]) for f in agent["findings"]]

    labels = agent["labels"]
    recipes: dict[str, int] = {}
    for scenario in agent["scenarios"]:
        recipes[scenario["recipe"]] = recipes.get(scenario["recipe"], 0) + 1
    blocks += [
        Heading("Setup", "agent-setup"),
        Table(
            ("Condition", "What the agent gets"),
            tuple((code(c), cell(labels[c])) for c in config["conditions"]),
        ),
        Table(
            ("Fact", "Value"),
            (
                (
                    cell("Agent"),
                    cell(f"opencode {config['opencode']}, build agent, --pure"),
                ),
                (cell("Models"), cell(", ".join(config["models"]))),
                (
                    cell("Scenarios"),
                    cell(", ".join(f"{k} {v}" for k, v in recipes.items())),
                ),
                (cell("Trials per cell"), num(config["trials"])),
                (cell("Run"), code(config["run_id"])),
                (cell("Commit"), code(config["git_hash"])),
            ),
        ),
    ]

    bars = []
    for g in _ordered(agent, summary["groups"]):
        if g["action"]:
            low, high = g["action"]["ci"]
            bars.append(
                {
                    "label": f"{short(g['model'])} · {g['condition']}",
                    "value": g["action"]["rate"],
                    "low": low,
                    "high": high,
                    "note": f"n={g['action']['n']}",
                }
            )
    blocks += [
        Heading("Gold action by condition", "agent-action"),
        Figure(
            "agent-action",
            lambda s: charts.hbars(
                "fig-agent-action",
                "Gold action by condition",
                "Share of sessions where the agent took the gold action.",
                bars,
                standalone=s,
            ),
            "Share of sessions in which the agent took the gold action, with 95% "
            "bootstrap intervals.",
            "Bar chart of gold-action accuracy by model and condition",
        ),
        _table(agent),
    ]

    deltas = [
        {
            "label": f"{short(d['model'])} · {d['condition']}",
            "value": d["delta"],
            "low": d["ci"][0],
            "high": d["ci"][1],
        }
        for d in summary["deltas"]
    ]
    if deltas:
        blocks += [
            Heading("Value of ember", "agent-value"),
            Para(
                "Each bar is the paired change in gold-action accuracy against the "
                "same scenarios and trials without ember."
            ),
            Figure(
                "agent-value",
                lambda s: charts_agent.diverging(
                    "fig-agent-value",
                    "Change in gold action vs no ember",
                    "Paired differences in gold-action accuracy.",
                    deltas,
                    standalone=s,
                ),
                "Paired change in gold-action accuracy against no ember, in "
                "percentage points, with 95% bootstrap intervals.",
                "Diverging bar chart of accuracy change versus no ember",
            ),
        ]

    ember_conditions = [c for c in config["conditions"] if c != "none"]
    asked_rows = tuple(
        (
            code(recipe),
            cell(", ".join(entry["recipe"])),
            cell(", ".join(f"{qid} ({n})" for qid, n in entry["top"])),
        )
        for recipe, entry in agent["asked"].items()
    )
    blocks += [
        Heading("By recipe", "agent-recipes"),
        Para("Gold-action accuracy by recipe for every model and condition:"),
        _pivot(agent, "action", list(config["conditions"])),
        Para("Consultation rate by recipe under the ember conditions:"),
        _pivot(agent, "consult", ember_conditions),
        Heading("Latency and ember overhead by recipe", "agent-latency"),
        Para(
            "Mean session wall-clock time with and without ember consulted, and the "
            "overhead ember adds. `per_call_ms` is the time the `ember_advise` tool "
            "call itself took inside the session, from opencode's event timestamps "
            "(only available in runs recorded with the current harness version)."
        ),
    ]
    lat = agent["summary"].get("latency_by_recipe") or {}
    if lat:
        lat_rows = tuple(
            (
                code(recipe),
                num(f"{v['with_ember_s']:.1f}s" if v.get("with_ember_s") else "n/a"),
                num(
                    f"{v['without_ember_s']:.1f}s"
                    if v.get("without_ember_s")
                    else "n/a"
                ),
                num(f"+{v['overhead_s']:.1f}s" if v.get("overhead_s") else "n/a"),
                num(f"{v['per_call_ms']:.0f}ms" if v.get("per_call_ms") else "n/a"),
            )
            for recipe, v in sorted(lat.items())
        )
        blocks.append(
            Table(
                (
                    "Recipe",
                    "With ember (mean)",
                    "No ember (mean)",
                    "Overhead",
                    "Per-call ms",
                ),
                lat_rows,
                caption="Overhead = with ember minus no ember across all models and "
                "conditions; per-call ms requires opencode timing events in the trace.",
                anchor="agent-latency-table",
            )
        )
    blocks += [
        Heading("Questions agents asked", "agent-questions"),
        Para(
            "The kit's recipes fix each decision's question set because ember "
            "weighs questions jointly. This table shows the question ids agents "
            "actually sent, with counts."
        ),
        Table(("Recipe", "Kit questions", "Most asked by agents"), asked_rows),
    ]

    keys = [(m, c) for m in config["models"] for c in config["conditions"]]
    scenario_rows = []
    for scenario in agent["scenarios"]:
        cells_ = summary["scenarios"].get(scenario["id"], {})
        scenario_rows.append(
            (
                code(scenario["id"]),
                code(scenario["gold_action"]),
                *(
                    num(f"{cells_[f'{m}|{c}']['passed']}/{cells_[f'{m}|{c}']['runs']}")
                    if f"{m}|{c}" in cells_
                    else num("n/a")
                    for m, c in keys
                ),
            )
        )
    blocks += [
        Heading("Per scenario", "agent-scenarios"),
        Table(
            ("Scenario", "Gold action", *(f"{short(m)} {c}" for m, c in keys)),
            tuple(scenario_rows),
            collapse=f"All {len(scenario_rows)} scenarios",
        ),
    ]
    if summary["invalid"]:
        blocks += [
            Heading("Invalid sessions", "agent-invalid"),
            Table(
                ("Model", "Condition", "Scenario", "Trial", "Timed out", "Exit"),
                tuple(
                    (
                        code(short(i["model"])),
                        code(i["condition"]),
                        code(i["scenario"]),
                        num(i["trial"]),
                        cell(str(i["timed_out"])),
                        num(i["exit_code"]),
                    )
                    for i in summary["invalid"]
                ),
            ),
        ]
    return ("agent", "Agent in the loop", blocks)
