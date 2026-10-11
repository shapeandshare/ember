"""Benchmark-design model: recipes, labels, and composition for the report.

Split out of ``evals/analysis.py`` (Article X §10.3). The recipe prose comes
from the single registry in ``evals/dataset/recipes.py``; the dataset supplies
each recipe's fixed question set.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .dataset import card as dataset_card
from .dataset.io import read_items
from .dataset.recipes import RECIPES
from .dataset.register import load as load_register
from .dataset.scales import scale_for

Record = dict[str, Any]

RECIPE_PROSE = ("title", "when", "state", "decides")


def option_text(spec: Mapping[str, Any], label: Any) -> str:
    """Return the option description for ``label`` under ``spec``."""
    criteria = spec.get("criteria")
    if spec["type"] == "noul":
        key = "true" if label else "false"
        return str(criteria[key]) if criteria else ("yes" if label else "no")
    return str(criteria[label])


def label_order(spec: Mapping[str, Any]) -> list[Any]:
    """Return the gold labels of ``spec`` in display order."""
    if spec["type"] == "noul":
        return [True, False]
    if spec["type"] == "score":
        return list(range(len(spec["criteria"])))
    return list(spec["criteria"])


def recipe_prose(category: str) -> dict[str, Any]:
    """Return the registry's prose fields for ``category`` (empty if unregistered)."""
    spec = RECIPES.get(category)
    if spec is None:
        return {}
    dumped = spec.model_dump(mode="json")
    prose = {key: dumped[key] for key in RECIPE_PROSE}
    prose.update(family=dumped["family"], risk=dumped["risk"], phase=dumped["phase"])
    prose["compliance"] = dumped["compliance"]
    return prose


def recipe_title(category: str) -> str:
    """Return the registry title for ``category``, or the category itself."""
    spec = RECIPES.get(category)
    return spec.title if spec is not None else category


def recipes(sources: Sequence[Record]) -> list[Record]:
    """Return one recipe entry per category: registry prose plus its question set."""
    first: dict[str, Record] = {}
    for item in sources:
        first.setdefault(item["category"], item)
    recipes = []
    for category, item in first.items():
        questions = []
        for qid, spec in item["questions"].items():
            criteria = spec.get("criteria")
            if isinstance(criteria, dict):
                options = [{"label": k, "text": v} for k, v in criteria.items()]
            elif isinstance(criteria, list):
                options = [{"label": i, "text": v} for i, v in enumerate(criteria)]
            else:
                options = []
            question: Record = {
                "id": qid,
                "type": spec["type"],
                "instructions": spec["instructions"],
                "options": options,
            }
            scale = scale_for(category, qid)
            if spec["type"] == "score" and scale is not None:
                question["legend"] = scale.legend(len(options))
                question["dangerous_end"] = scale.dangerous_end.value
            questions.append(question)
        recipes.append(
            {
                "category": category,
                **recipe_prose(category),
                "questions": questions,
            }
        )
    return recipes


def composition(sources: Sequence[Record]) -> Record:
    """Return per-recipe item counts by split, per-label counts, and source counts."""
    recipes: dict[str, Record] = {}
    labels: dict[str, Record] = {}
    for item in sources:
        row = recipes.setdefault(
            item["category"],
            {
                "category": item["category"],
                "title": recipe_title(item["category"]),
                "items": 0,
                "dev": 0,
                "test": 0,
                "questions": list(item["questions"]),
            },
        )
        row["items"] += 1
        row[item["split"]] += 1
        for qid, gold in item["gold_labels"].items():
            spec = item["questions"][qid]
            entry = labels.setdefault(
                qid, {"type": spec["type"], "spec": spec, "counts": {}}
            )
            counts = entry["counts"].setdefault(
                json.dumps(gold),
                {"label": gold, "text": option_text(spec, gold), "dev": 0, "test": 0},
            )
            counts[item["split"]] += 1
    for entry in labels.values():
        order = [json.dumps(label) for label in label_order(entry.pop("spec"))]
        counts = entry.pop("counts")
        entry["labels"] = [counts[key] for key in order if key in counts]
    worked = sum(1 for i in sources if _reproduces_skill_example(i.get("source")))
    by_kind: dict[str, int] = {}
    for item in sources:
        kind = _source_kind(item.get("source"))
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "recipes": list(recipes.values()),
        "labels": labels,
        "sources": {
            "skill_md": worked,
            "curated": len(sources) - worked,
            "by_kind": dict(sorted(by_kind.items())),
        },
    }


def _source_kind(source: Any) -> str:
    """Return the source kind of a typed source, or ``authored`` for a legacy string."""
    if isinstance(source, Mapping):
        return str(source.get("kind", "authored"))
    return "authored"


def _reproduces_skill_example(source: Any) -> bool:
    """Whether an item reproduces one of the agent kit's worked examples."""
    if isinstance(source, str):
        return source == "skill_md"
    if isinstance(source, Mapping):
        return "SKILL.md" in str(source.get("note") or "")
    return False


def scales_text(recipe_rows: Sequence[Record]) -> list[Record]:
    """Return one ``{question, category, legend, dangerous_end}`` per score question."""
    rows: list[Record] = []
    for recipe in recipe_rows:
        for question in recipe["questions"]:
            if question["type"] == "score" and "legend" in question:
                rows.append(
                    {
                        "question": question["id"],
                        "category": recipe["category"],
                        "legend": question["legend"],
                        "dangerous_end": question["dangerous_end"],
                    }
                )
    return rows


def generated_card(
    dataset_path: Path, register_sha256: str | None, legacy_version: str | None
) -> Record | None:
    """Build the generated dataset card for the dataset a run scored (FR-033).

    Parameters
    ----------
    dataset_path : Path
        The exact dataset file the run scored (the bundle's copy, not the
        checkout's), so an older bundle describes its own items.
    register_sha256 : str | None
        The register hash the run recorded, copied into the card.
    legacy_version : str | None
        The value a pre-Phase-0 dataset's string sources are mapped with (its
        file hash, as ``snapshot_evals.rebuild`` does); unused otherwise.

    Returns
    -------
    dict[str, Any] | None
        ``card.build``'s output without lint gaps (the lint belongs to the
        checkout's dataset and lock), or ``None`` when the file is missing.
    """
    if not dataset_path.exists():
        return None
    try:
        items = read_items(dataset_path)
    except ValueError:
        items = read_items(dataset_path, legacy_dataset_version=legacy_version)
    return dataset_card.build(
        items,
        load_register(),
        [],
        register_sha256=register_sha256,
        generated_from=dataset_path.name,
    )
