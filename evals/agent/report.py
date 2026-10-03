"""Report model for an agent-in-the-loop run, for the reviewer export.

``build(results_path)`` reads an ``agent_*_results.json`` and its trace and
returns the tables and findings ``evals.sections_agent`` renders. Findings are
derived from the numbers, never written by hand.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .. import metrics
from .sandbox import CONDITION_LABELS
from .scenarios import RECIPE_QUESTIONS, SCENARIOS

Record = dict[str, Any]
NARRATIVE = [
    "This section measures ember the way it is used: through a coding agent. Each "
    "session gives opencode a realistic request inside a throwaway git repo at a "
    "point where the agent kit says to consult ember (or, for controls, where "
    "there is no judgment call). The gold action is judged only from what the "
    "agent did (files, commits, tests, its reply), so the same scenarios score "
    "the agent with and without ember.",
    "Every session runs `opencode run --pure` with a private HOME and XDG "
    "directories and no TCP port, so the user's opencode config, plugins, sessions, "
    "and running instances are never touched. The four conditions add the agent "
    "kit's channels one at a time.",
]


FLOW = {
    "nodes": [
        {
            "id": "scenario",
            "label": "Scenario",
            "detail": "prompt, repo spec, gold checks",
        },
        {
            "id": "sandbox",
            "label": "Sandbox",
            "detail": "git repo, private HOME and XDG, condition files",
        },
        {
            "id": "agent",
            "label": "opencode run",
            "detail": "--pure --format json, no TCP port",
        },
        {
            "id": "judge",
            "label": "Judge",
            "detail": "gold checks, consulted, kit questions, follows ember",
        },
        {
            "id": "ember",
            "label": "ember",
            "below": "agent",
            "detail": "ember-mcp to the model server",
        },
        {
            "id": "summary",
            "label": "Summary",
            "below": "judge",
            "detail": "per model and condition, paired change vs none",
        },
    ],
    "edges": [
        {"from": "scenario", "to": "sandbox", "label": "build"},
        {"from": "sandbox", "to": "agent", "label": "run"},
        {"from": "agent", "to": "judge", "label": "effects"},
        {"from": "agent", "to": "ember", "label": "ember_advise", "style": "dashed"},
        {"from": "judge", "to": "summary", "label": "aggregate"},
    ],
}
FLOW_TEXT = """scenario: prompt, repo spec, gold checks
   │
   ▼ build
sandbox: git repo, private HOME and XDG, condition files
   │
   ▼ opencode run --pure --format json (no TCP port)
coding agent ──ember_advise──► ember-mcp ──HTTP──► model server
   │         ◄────answers─────
   ▼ files, commits, tests, final reply
judge: gold checks, consulted, before acting, kit questions, follows ember
   │
   ▼
summary: per model and condition, paired change against no ember"""


def short(model: str) -> str:
    """Return a model id without its provider prefix."""
    return model.split("/")[-1]


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _findings(summary: Record, records: list[Record]) -> list[Record]:
    findings: list[Record] = []
    groups = {(g["model"], g["condition"]): g for g in summary["groups"]}
    for delta in summary["deltas"]:
        if delta["condition"] != "full":
            continue
        model = delta["model"]
        with_kit = groups[(model, "full")]["action"]
        without = groups.get((model, "none"), {}).get("action")
        low, high = delta["ci"]
        tone = "good" if low > 0 else "warn" if high < 0 else "info"
        findings.append(
            {
                "tone": tone,
                "title": f"{short(model)}: value of the full kit",
                "text": f"With the full agent kit, {short(model)} took the gold "
                "action in "
                f"{_pct(with_kit['rate'])} of sessions, against "
                f"{_pct(without['rate']) if without else 'n/a'} without ember: "
                f"{delta['delta'] * 100:+.1f} points (95% CI {low * 100:+.1f} to "
                f"{high * 100:+.1f}, {delta['n']} paired sessions).",
            }
        )
    consults = [
        (g, g["consult"])
        for g in summary["groups"]
        if g["condition"] != "none" and g["consult"]
    ]
    if consults:
        low_g, low = min(consults, key=lambda x: x[1]["rate"])
        high_g, high = max(consults, key=lambda x: x[1]["rate"])
        findings.append(
            {
                "tone": "warn" if low["rate"] < 0.5 else "info",
                "title": "How often agents consult ember",
                "text": "At decision points, consultation ranged from "
                f"{_pct(low['rate'])} "
                f"({short(low_g['model'])}, {low_g['condition']}) to "
                f"{_pct(high['rate'])} ({short(high_g['model'])}, "
                f"{high_g['condition']}).",
            }
        )
    by_recipe: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        if r["valid"] and r["condition"] != "none" and r["kind"] == "decision":
            by_recipe[r["recipe"]].append(bool(r["consulted"]))
    if by_recipe:
        rates = {k: sum(v) / len(v) for k, v in by_recipe.items()}
        weakest = min(rates, key=rates.__getitem__)
        findings.append(
            {
                "tone": "info",
                "title": "Where consultation is weakest",
                "text": "Across ember conditions, consultation was lowest for "
                f"{weakest} ({_pct(rates[weakest])}) and highest for "
                f"{max(rates, key=rates.__getitem__)} ({_pct(max(rates.values()))}).",
            }
        )
    fidelity = [
        r["recipe_fidelity"]
        for r in records
        if r["valid"] and r["consulted"] and r["recipe_fidelity"] is not None
    ]
    if fidelity:
        share = sum(fidelity) / len(fidelity)
        findings.append(
            {
                "tone": "warn" if share < 0.7 else "good",
                "title": "Do agents ask the kit's questions?",
                "text": f"{_pct(share)} of consultations asked every question of the "
                "kit's recipe; the rest wrote their own question sets, which ember has "
                "not been "
                "calibrated on.",
            }
        )
    followed = [
        r["followed"] for r in records if r["valid"] and r["followed"] is not None
    ]
    if followed:
        findings.append(
            {
                "tone": "info",
                "title": "Do agents follow ember?",
                "text": "When ember's answer implied an action under the kit's "
                "rules, the "
                f"agent took that action in {_pct(sum(followed) / len(followed))} of "
                f"{len(followed)} sessions.",
            }
        )
    over = [
        r["consulted"]
        for r in records
        if r["valid"] and r["kind"] == "control" and r["condition"] != "none"
    ]
    if over:
        findings.append(
            {
                "tone": "info",
                "title": "Unneeded consultations",
                "text": "On control tasks with no judgment call, agents consulted "
                "ember "
                f"in {_pct(sum(over) / len(over))} of {len(over)} sessions.",
            }
        )
    return findings


def build(results_path: Path) -> Record:
    """Build the agent report model for one ``agent_*_results.json``."""
    data = json.loads(results_path.read_text(encoding="utf-8"))
    config, summary = data["config"], data["summary"]
    trace = results_path.with_name(config["trace"])
    records = [
        json.loads(line)
        for line in trace.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    asked: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        if record["valid"] and record["consulted"]:
            asked[record["recipe"]].update(record["asked"])
    scenarios = {s["id"]: s for s in SCENARIOS}
    report: Record = {
        "config": config,
        "summary": summary,
        "narrative": NARRATIVE,
        "flow": FLOW,
        "flow_text": FLOW_TEXT,
        "labels": {c: CONDITION_LABELS.get(c, c) for c in config["conditions"]},
        "cost_total": sum(float(r["cost"]) for r in records),
        "findings": _findings(summary, records),
        "asked": {
            recipe: {
                "recipe": sorted(RECIPE_QUESTIONS.get(recipe, ())),
                "top": counts.most_common(8),
            }
            for recipe, counts in sorted(asked.items())
        },
        "scenarios": [
            {
                "id": sid,
                "recipe": scenarios[sid]["recipe"],
                "gold_action": scenarios[sid]["gold_action"],
                "rationale": scenarios[sid]["rationale"],
                "prompt": scenarios[sid]["prompt"],
            }
            for sid in config["scenarios"]
            if sid in scenarios
        ],
        "results_file": results_path.name,
    }
    rounded: Record = metrics.rounded(report)
    return rounded
