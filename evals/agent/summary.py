"""Aggregate scored agent sessions per model and condition.

Rates carry 95% bootstrap intervals (``evals.metrics.bootstrap_ci``). The
headline comparison is each ember condition against ``none`` on the same
scenarios and trials: the paired difference in gold-action accuracy.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from .. import metrics
from .condition import Condition

Record = dict[str, Any]


def rate(flags: Sequence[bool | None]) -> Record | None:
    """Return ``{n, rate, ci}`` over the non-``None`` flags, or ``None``."""
    values = [float(f) for f in flags if f is not None]
    if not values:
        return None
    return {
        "n": len(values),
        "rate": sum(values) / len(values),
        "ci": metrics.bootstrap_ci(values),
    }


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _group(records: Sequence[Record]) -> Record:
    decision = [r for r in records if r["kind"] == "decision"]
    control = [r for r in records if r["kind"] == "control"]
    consulted = [r for r in decision if r["consulted"]]
    return {
        "runs": len(records),
        "action": rate([r["action_ok"] for r in records]),
        "decision_action": rate([r["action_ok"] for r in decision]),
        "consult": rate([r["consulted"] for r in decision]),
        "over_consult": rate([r["consulted"] for r in control]),
        "before_act": rate([r["before_act"] for r in consulted]),
        "recipe_fidelity": rate([r["recipe_fidelity"] for r in consulted]),
        "evidence": rate([r["evidence"] for r in consulted]),
        "followed": rate([r["followed"] for r in consulted]),
        "call_quality": (
            _mean(
                [
                    float((r.get("call_quality") or {}).get("score") or 0)
                    for r in consulted
                    if (r.get("call_quality") or {}).get("score") is not None
                ]
            )
            if consulted
            else None
        ),
        "cq_batched": rate(
            [(r.get("call_quality") or {}).get("batched") for r in consulted]
        ),
        "cq_verdict_free": rate(
            [(r.get("call_quality") or {}).get("verdict_free") for r in consulted]
        ),
        "cq_ids_correct": rate(
            [(r.get("call_quality") or {}).get("ids_correct") for r in consulted]
        ),
        "calls_per_run": _mean([float(r["ember_calls"]) for r in records]),
        "ember_ms_mean": _mean(
            [float(r["ember_ms_mean"]) for r in records if r.get("ember_ms_mean")]
        ),
        "cost": _mean([float(r["cost"]) for r in records]),
        "cost_total": sum(float(r["cost"]) for r in records),
        "seconds": _mean([float(r["seconds"]) for r in records]),
        "steps": _mean([float(r.get("steps", 0)) for r in records]),
    }


def _latency_by_recipe(valid: Sequence[Record]) -> dict[str, Any]:
    """Per-recipe mean session latency, split by whether ember was consulted."""
    # import-placement:allow - deferred to avoid defaultdict at module load
    from collections import defaultdict as _dd

    by: dict[str, dict[str, list[float]]] = _dd(
        lambda: {"ember": [], "no_ember": [], "ember_ms": []}
    )
    for r in valid:
        recipe = r["recipe"]
        bucket = "ember" if r["consulted"] else "no_ember"
        by[recipe][bucket].append(float(r["seconds"]))
        if r.get("ember_ms_mean") is not None:
            by[recipe]["ember_ms"].append(float(r["ember_ms_mean"]))
    result = {}
    for recipe, buckets in sorted(by.items()):
        e, ne = buckets["ember"], buckets["no_ember"]
        ms = buckets["ember_ms"]
        result[recipe] = {
            "with_ember_s": _mean(e) if e else None,
            "without_ember_s": _mean(ne) if ne else None,
            "overhead_s": (round(_mean(e) - _mean(ne), 2) if e and ne else None),
            "per_call_ms": _mean(ms) if ms else None,
        }
    return result


def summarize(records: Sequence[Record]) -> Record:
    """Return the agent-eval summary for all scored sessions."""
    valid = [r for r in records if r["valid"]]
    groups: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for record in valid:
        groups[(record["model"], record["condition"])].append(record)
    by_recipe: dict[tuple[str, str, str], list[Record]] = defaultdict(list)
    for record in valid:
        by_recipe[(record["model"], record["condition"], record["recipe"])].append(
            record
        )

    deltas = []
    for (model, condition), rows in sorted(groups.items()):
        if condition == Condition.NONE:
            continue
        base = {
            (r["scenario"], r["trial"]): r["action_ok"]
            for r in groups.get((model, Condition.NONE), [])
        }
        pairs = [
            float(r["action_ok"]) - float(base[(r["scenario"], r["trial"])])
            for r in rows
            if (r["scenario"], r["trial"]) in base
        ]
        if pairs:
            deltas.append(
                {
                    "model": model,
                    "condition": condition,
                    "n": len(pairs),
                    "delta": sum(pairs) / len(pairs),
                    "ci": metrics.bootstrap_ci(pairs),
                }
            )

    scenarios: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for record in valid:
        key = f"{record['model']}|{record['condition']}"
        scenarios[record["scenario"]][key].append(bool(record["action_ok"]))

    flags = [float(r["action_ok"]) for r in valid]
    result = {
        "overall": {
            "runs": len(valid),
            "accuracy": _mean(flags),
            "accuracy_ci": metrics.bootstrap_ci(flags),
            "item_accuracy": _mean(flags),  # 1 check per session = item = question
            "wrong_actions": sum(
                1
                for r in valid
                if r.get("kit_decision")
                and r.get("observed_action")
                and r["kit_decision"] != r["observed_action"]
            ),
        },
        "runs": len(records),
        "valid": len(valid),
        "invalid": [
            {
                "model": r["model"],
                "condition": r["condition"],
                "scenario": r["scenario"],
                "trial": r["trial"],
                "timed_out": r["timed_out"],
                "exit_code": r["exit_code"],
                "errors": r["errors"][:2],
                "stderr": r["stderr"][-300:],
            }
            for r in records
            if not r["valid"]
        ],
        "groups": [
            {"model": m, "condition": c, **_group(rows)}
            for (m, c), rows in sorted(groups.items())
        ],
        "deltas": deltas,
        "recipes": [
            {
                "model": m,
                "condition": c,
                "recipe": recipe,
                "action": rate([r["action_ok"] for r in rows]),
                "consult": rate([r["consulted"] for r in rows]),
            }
            for (m, c, recipe), rows in sorted(by_recipe.items())
        ],
        "scenarios": {
            sid: {k: {"passed": sum(v), "runs": len(v)} for k, v in cells.items()}
            for sid, cells in sorted(scenarios.items())
        },
        "latency_by_recipe": _latency_by_recipe(valid),
    }
    rounded: Record = metrics.rounded(result)
    return rounded
