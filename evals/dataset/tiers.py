"""Difficulty tiers: tag the items every leaderboard row got fully right."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .hashes import dataset_content_sha256
from .io import DATASET_PATH, read_items, write_items
from .records.item import Item

BENCHMARK_DIR = Path(__file__).resolve().parents[2] / "benchmark"


def easy_ids(
    rows: Sequence[Mapping[str, Any]],
    traces: Mapping[str, Sequence[Mapping[str, Any]]],
) -> set[str]:
    """Return the ids every row's producing run scored fully correct.

    Parameters
    ----------
    rows : Sequence[Mapping[str, Any]]
        Leaderboard rows on the current version; each has ``recipes`` mapping a
        category to ``{"run_id": ...}``.
    traces : Mapping[str, Sequence[Mapping[str, Any]]]
        Scored trace rows by run id (``id``, ``category``, ``correct``).

    Returns
    -------
    set[str]
        Item ids that are easy: scored by at least one row and never missed.
    """
    correct_by_item: dict[str, list[bool]] = {}
    for row in rows:
        for category, column in row["recipes"].items():
            for record in traces.get(column["run_id"], []):
                if record["category"] != category:
                    continue
                correct_by_item.setdefault(record["id"], []).append(
                    bool(record["correct"])
                )
    return {
        item_id for item_id, flags in correct_by_item.items() if flags and all(flags)
    }


def apply(items: Sequence[Item], ids: set[str]) -> list[Item]:
    """Return ``items`` with ``tier="easy"`` on ``ids`` and cleared elsewhere."""
    return [
        item.model_copy(update={"tier": "easy" if item.id in ids else None})
        for item in items
    ]


def _load_traces(benchmark: Path, run_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    traces: dict[str, list[dict[str, Any]]] = {}
    for run_id in run_ids:
        path = benchmark / run_id / "trace.jsonl"
        if path.exists():
            traces[run_id] = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
    return traces


def current_rows(benchmark: Path, content_sha256: str) -> list[dict[str, Any]]:
    """Return the leaderboard rows for the dataset version ``content_sha256``."""
    # import-placement:allow - leaderboard imports dataset.recipes; keep it one-way
    from ..leaderboard import build

    models = []
    for bundle in sorted(benchmark.glob("*/model.json")):
        models.append(json.loads(bundle.read_text(encoding="utf-8")))
    for version in build(models).get("versions", []):
        if version.get("dataset_content_sha256") == content_sha256:
            rows: list[dict[str, Any]] = version["rows"]
            return rows
    return []


def main(argv: Sequence[str] | None = None) -> int:
    """Tag easy items from the current version's rows (``ember eval dataset tier``)."""
    parser = argparse.ArgumentParser(prog="ember eval dataset tier")
    parser.add_argument("--from", dest="benchmark", type=Path, default=BENCHMARK_DIR)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    args = parser.parse_args(argv)
    items = read_items(args.dataset)
    content = dataset_content_sha256(items)
    rows = current_rows(args.benchmark, content)
    if not rows:
        print(
            f"error: no leaderboard row on dataset version {content[:12]} "
            f"in {args.benchmark}"
        )
        return 1
    run_ids = {column["run_id"] for row in rows for column in row["recipes"].values()}
    ids = easy_ids(rows, _load_traces(args.benchmark, run_ids))
    tagged = apply(items, ids)
    added = sum(
        1
        for before, after in zip(items, tagged, strict=True)
        if not before.tier and after.tier
    )
    removed = sum(
        1
        for before, after in zip(items, tagged, strict=True)
        if before.tier and not after.tier
    )
    if dataset_content_sha256(tagged) != content:
        print("error: tagging changed the dataset content hash; nothing written")
        return 1
    write_items(args.dataset, tagged)
    print(f"easy: {len(ids)} (+{added} / -{removed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
