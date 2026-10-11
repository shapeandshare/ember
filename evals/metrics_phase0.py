"""Summary blocks added to ``metrics.aggregate`` by specs/004 Phase 0.

Capability (non-headline recipes), risk (asymmetric metrics for risk recipes),
tokens (accuracy and Brier by state length), consistency (variant groups),
by-source-kind, and tiers (non-easy accuracy). Each reads the scored items and
the annotations their trace rows carry.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any

from . import risk_metrics
from .dataset.recipes import RECIPES
from .dataset.records.source import VARIANT_PERTURBATIONS
from .dataset.scales import SCALES
from .metric_functions import bootstrap_ci, brier_binary, brier_multiclass

Record = dict[str, Any]
Result = Mapping[str, Any]

TOKEN_BIN_EDGES = (
    0,
    32,
    64,
    128,
    256,
    512,
    1024,
    2048,
    4096,
    8192,
    16384,
    32768,
    65536,
)


def is_headline(category: str) -> bool:
    """Whether ``category`` counts toward the headline (unregistered recipes do)."""
    spec = RECIPES.get(category)
    return spec.headline if spec is not None else True


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _records(results: Sequence[Result]) -> list[Record]:
    return [
        {
            **question,
            "question": qid,
            "id": result["id"],
            "category": result["category"],
        }
        for result in results
        for qid, question in result["questions"].items()
    ]


def _block(results: Sequence[Result]) -> Record:
    records = _records(results)
    flags = [float(r["correct"]) for r in records]
    return {
        "items": len(results),
        "questions": len(records),
        "accuracy": _mean(flags),
        "accuracy_ci": bootstrap_ci(flags),
        "item_accuracy": _mean([float(r["correct"]) for r in results]),
    }


def capability(results: Sequence[Result]) -> Record | None:
    """Summarise the non-headline recipes, or ``None`` when none were scored."""
    rows = [r for r in results if not is_headline(str(r["category"]))]
    if not rows:
        return None
    by_category: dict[str, list[Result]] = defaultdict(list)
    for row in rows:
        by_category[str(row["category"])].append(row)
    block = _block(rows)
    block["categories"] = {
        category: _block(members) for category, members in sorted(by_category.items())
    }
    return block


def risk(results: Sequence[Result]) -> Record:
    """Asymmetric metrics per risk recipe present in ``results``."""
    by_category: dict[str, list[Result]] = defaultdict(list)
    for row in results:
        by_category[str(row["category"])].append(row)
    summary: Record = {}
    for category, members in sorted(by_category.items()):
        spec = RECIPES.get(category)
        if spec is None or not spec.risk:
            continue
        summary[category] = risk_metrics.summarize(_records(members), spec, SCALES)
    return summary


def _brier(records: Sequence[Record]) -> float | None:
    scored = []
    for r in records:
        if r["type"] == "choice":
            scored.append(brier_multiclass([r["probabilities"]], [r["gold"]]))
        elif r["type"] == "noul":
            scored.append(brier_binary([r["p_true"]], [bool(r["gold"])]))
    return _mean(scored) if scored else None


def tokens(results: Sequence[Result]) -> Record | None:
    """Accuracy and Brier by state-token bin; ``None`` without ``tokens`` rows."""
    rows = [r for r in results if isinstance(r.get("tokens"), Mapping)]
    if not rows:
        return None
    states = sorted(int(r["tokens"]["state"]) for r in rows)
    middle = len(states) // 2
    median = (
        float(states[middle])
        if len(states) % 2
        else (states[middle - 1] + states[middle]) / 2
    )
    bins: list[Record] = []
    for low, high in pairwise(TOKEN_BIN_EDGES):
        members = [r for r in rows if low <= int(r["tokens"]["state"]) < high]
        if not members:
            continue
        records = _records(members)
        bins.append(
            {
                "low": low,
                "high": high,
                "n": len(members),
                "accuracy": _mean([float(r["correct"]) for r in records]),
                "brier": _brier(records),
            }
        )
    return {"median_state": median, "max_state": states[-1], "state_bins": bins}


def consistency(results: Sequence[Result]) -> Record:
    """Per recipe: variant groups and the share whose members all agree."""
    by_id = {str(r["id"]): r for r in results}
    groups: dict[str, list[Result]] = defaultdict(list)
    for row in results:
        if row.get("perturbation") in VARIANT_PERTURBATIONS and row.get("parent_id"):
            parent_id = str(row["parent_id"])
            if parent_id in by_id and by_id[parent_id] not in groups[parent_id]:
                groups[parent_id].append(by_id[parent_id])
            groups[parent_id].append(row)
    per_recipe: dict[str, list[bool]] = defaultdict(list)
    for members in groups.values():
        category = str(members[0]["category"])
        predictions = {
            tuple(
                (qid, str(q["predicted"]))
                for qid, q in sorted(member["questions"].items())
            )
            for member in members
        }
        per_recipe[category].append(len(predictions) == 1)
    return {
        category: {"groups": len(flags), "agreement": _mean([float(f) for f in flags])}
        for category, flags in sorted(per_recipe.items())
    }


def by_source_kind(results: Sequence[Result]) -> Record:
    """Per recipe holding more than one source kind: items and accuracy per kind."""
    by_category: dict[str, dict[str, list[Result]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in results:
        kind = row.get("source_kind")
        if kind:
            by_category[str(row["category"])][str(kind)].append(row)
    summary: Record = {}
    for category, kinds in sorted(by_category.items()):
        if len(kinds) < 2:
            continue
        summary[category] = {}
        for kind, members in sorted(kinds.items()):
            records = _records(members)
            summary[category][kind] = {
                "items": len(members),
                "accuracy": _mean([float(r["correct"]) for r in records]),
                "item_accuracy": _mean([float(r["correct"]) for r in members]),
            }
    return summary


def tiers(results: Sequence[Result]) -> Record | None:
    """Easy counts and non-easy accuracy, or ``None`` when no row carries a tier."""
    if not any(r.get("tier") for r in results):
        return None
    easy = [r for r in results if r.get("tier") == "easy"]
    non_easy = [r for r in results if r.get("tier") != "easy"]
    block = (
        _block(non_easy) if non_easy else {"items": 0, "questions": 0, "accuracy": 0.0}
    )
    return {
        "easy_items": len(easy),
        "easy_questions": len(_records(easy)),
        "non_easy": block,
    }
