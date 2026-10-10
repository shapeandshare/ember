"""Item selection, the exploratory subset, and manifest assembly (research R9, R13)."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import random
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ember import models

from ..eval import provenance
from .filler import FILLER_LICENCE, FILLER_PATH, FILLER_SHA256, FILLER_SOURCE
from .records.depth import Depth
from .records.probe_manifest import EXPLORATORY_ITEMS, SEED, ProbeManifest
from .records.probe_model import ProbeModel

DATASET_PATH = provenance.REPO_ROOT / "evals" / "clef-flash.jsonl"
#: Items whose unpadded request exceeds this leave too little room at 2K.
UNPADDED_LIMIT = 2048 - 64
MEDIA_KEYS = ("images", "videos")
MEMORY_BUDGETS = {"flash": 32 * 2**30, "full": 64 * 2**30}


def load_items(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    """Read the benchmark dataset, one item per line."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def select_items(
    dataset: Sequence[dict[str, Any]],
    count: Callable[[dict[str, Any]], int],
    *,
    limit: int = UNPADDED_LIMIT,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Keep the text-only items that fit; record every exclusion with its reason.

    ``count`` returns an item's unpadded encoded request size.
    """
    kept: list[dict[str, Any]] = []
    excluded: dict[str, str] = {}
    for item in dataset:
        if any(item.get(key) for key in MEDIA_KEYS):
            excluded[item["id"]] = "media item"
            continue
        size = count(item)
        if size > limit:
            excluded[item["id"]] = f"unpadded request is {size} tokens, over {limit}"
            continue
        kept.append(item)
    return kept, excluded


def exploratory_subset(
    pool: Sequence[Mapping[str, Any]], size: int, seed: int
) -> list[str]:
    """Draw ``size`` item ids stratified by category, seeded, in pool order.

    Each category gets its proportional share (largest remainder, ties by
    name); with ``size`` at or above the pool, every item is returned.
    """
    order = [str(item["id"]) for item in pool]
    if size >= len(order):
        return order
    groups: dict[str, list[str]] = defaultdict(list)
    for item in pool:
        groups[str(item["category"])].append(str(item["id"]))
    categories = sorted(groups)
    exact = {name: size * len(groups[name]) / len(order) for name in categories}
    quotas = {name: int(exact[name]) for name in categories}
    by_remainder = sorted(
        categories, key=lambda name: (quotas[name] - exact[name], name)
    )
    for name in by_remainder[: size - sum(quotas.values())]:
        quotas[name] += 1
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling, not security
    chosen: set[str] = set()
    for name in categories:
        chosen.update(rng.sample(groups[name], quotas[name]))
    return [item_id for item_id in order if item_id in chosen]


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(provenance.REPO_ROOT))
    except ValueError:
        return str(path)


def _ember_version() -> str:
    try:
        return importlib.metadata.version("ember-advise")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def probe_model(name: str, recommended_max_memory: int | None = None) -> ProbeModel:
    """Describe a registered model with its pre-declared memory budget."""
    spec = models.get(name)
    return ProbeModel(
        name=spec.name,
        repo=spec.repo,
        revision=spec.revision,
        params=spec.params,
        memory_budget_bytes=MEMORY_BUDGETS[spec.name],
        recommended_max_memory_bytes=recommended_max_memory,
    )


def provenance_fields() -> dict[str, Any]:
    """Return the run-time provenance a manifest records."""
    return {
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_hash": provenance.git_hash(),
        "git_dirty": provenance.git_dirty(),
        "ember_version": _ember_version(),
        "host": {**provenance.host_info(), "ram_bytes": provenance.ram_bytes()},
    }


def build_manifest(
    *,
    run_id: str,
    canonical: bool,
    model_names: Sequence[str],
    kept: Sequence[dict[str, Any]],
    excluded: dict[str, str],
    lengths: Sequence[int],
    dataset_path: Path = DATASET_PATH,
    recommended_max_memory: int | None = None,
) -> ProbeManifest:
    """Assemble a manifest; a dirty tree is never canonical."""
    fields = provenance_fields()
    size = min(EXPLORATORY_ITEMS, len(kept))
    return ProbeManifest(
        run_id=run_id,
        canonical=canonical and not fields["git_dirty"],
        device="mps",
        dtype="float16",
        models={
            name: probe_model(name, recommended_max_memory) for name in model_names
        },
        dataset_path=_relative(dataset_path),
        dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        item_ids=[str(item["id"]) for item in kept],
        excluded=excluded,
        filler_path=_relative(FILLER_PATH),
        filler_sha256=FILLER_SHA256,
        filler_source=FILLER_SOURCE,
        filler_licence=FILLER_LICENCE,
        lengths=list(lengths),
        depths=list(Depth),
        exploratory_items=size,
        exploratory_item_ids=exploratory_subset(kept, size, SEED),
        **fields,
    )
