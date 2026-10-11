"""Assign new items to ``dev``/``test`` deterministically and pin them in a lock."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..atomic import write_atomic
from .io import DATASET_PATH, read_items
from .records.item import Item
from .records.source_kind import SourceKind
from .records.split import Split

LOCK_PATH = Path(__file__).resolve().parent / "splits.lock"
DEV_TARGET = 0.4


def read_lock(path: Path = LOCK_PATH) -> dict[str, Split]:
    """Return the committed ``{item_id: split}`` map (empty when absent)."""
    if not path.exists():
        return {}
    raw: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return {item_id: Split(split) for item_id, split in raw.items()}


def append_lock(path: Path, assignments: Mapping[str, Split]) -> None:
    """Add new ids to the lock; an existing id's split can never change.

    Parameters
    ----------
    path : Path
        The lock file.
    assignments : Mapping[str, Split]
        Ids to add with their splits.

    Raises
    ------
    ValueError
        If an id is already pinned to a different split.
    """
    lock = read_lock(path)
    for item_id, split in assignments.items():
        pinned = lock.get(item_id)
        if pinned is not None and pinned is not split:
            raise ValueError(f"{item_id} is pinned to {pinned.value}; it cannot move")
        lock[item_id] = split
    write_atomic(
        path, json.dumps({k: v.value for k, v in sorted(lock.items())}, indent=2) + "\n"
    )


def _strata(item: Item) -> list[tuple[str, str, str]]:
    return [
        (item.category, qid, json.dumps(gold, sort_keys=True))
        for qid, gold in sorted(item.gold_labels.items())
    ]


def _family_key(item: Item) -> tuple[str, str] | None:
    source = item.source
    if source.kind is SourceKind.perturbed and source.parent_id:
        return ("parent", source.parent_id)
    if source.kind is SourceKind.templated and source.family:
        return ("template", source.family)
    if source.kind is SourceKind.imported and source.register_row and source.record_id:
        return ("record", f"{source.register_row}:{source.record_id}")
    return None


def assign_new(items: Sequence[Item], lock: Mapping[str, Split]) -> dict[str, Split]:
    """Assign every unlocked item a split, deterministically.

    Items are visited in id order. Each goes to the split that most reduces the
    maximum deviation from the 40/60 target across its own
    ``(category, question, label)`` strata, ties to ``test``; a perturbed item
    follows its parent, a templated item the first member of its family, and an
    imported item any earlier item from the same external record.

    Parameters
    ----------
    items : Sequence[Item]
        The whole dataset, locked and unlocked items alike.
    lock : Mapping[str, Split]
        The committed pins.

    Returns
    -------
    dict[str, Split]
        Assignments for the unlocked items only.
    """
    counts: dict[tuple[str, str, str], dict[Split, int]] = defaultdict(
        lambda: {Split.dev: 0, Split.test: 0}
    )
    families: dict[tuple[str, str], Split] = {}
    by_id = {item.id: item for item in items}
    for item in items:
        if item.id in lock:
            for stratum in _strata(item):
                counts[stratum][lock[item.id]] += 1
            key = _family_key(item)
            if key is not None:
                families.setdefault(key, lock[item.id])
    assigned: dict[str, Split] = {}

    def resolved(item_id: str) -> Split | None:
        return lock.get(item_id) or assigned.get(item_id)

    for item in sorted((i for i in items if i.id not in lock), key=lambda i: i.id):
        choice: Split | None = None
        source = item.source
        if source.kind is SourceKind.perturbed and source.parent_id in by_id:
            choice = resolved(source.parent_id or "")
        key = _family_key(item)
        if choice is None and key is not None:
            choice = families.get(key)
        if choice is None:
            choice = _least_deviating(item, counts)
        assigned[item.id] = choice
        if key is not None:
            families.setdefault(key, choice)
        for stratum in _strata(item):
            counts[stratum][choice] += 1
    return assigned


def _least_deviating(
    item: Item, counts: Mapping[tuple[str, str, str], Mapping[Split, int]]
) -> Split:
    def worst(split: Split) -> float:
        deviation = 0.0
        for stratum in _strata(item):
            dev = counts[stratum][Split.dev] + (1 if split is Split.dev else 0)
            test = counts[stratum][Split.test] + (1 if split is Split.test else 0)
            share = dev / (dev + test)
            deviation = max(deviation, abs(share - DEV_TARGET))
        return deviation

    if worst(Split.dev) < worst(Split.test):
        return Split.dev
    return Split.test


def main(argv: Sequence[str] | None = None) -> int:
    """Seed or extend the lock from a dataset (``python -m evals.dataset.splitting``).

    Parameters
    ----------
    argv : Sequence[str] | None
        Command-line arguments.

    Returns
    -------
    int
        Process exit code.
    """
    parser = argparse.ArgumentParser(prog="evals.dataset.splitting")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    parser.add_argument(
        "--init",
        action="store_true",
        help="pin every item to the split it already carries",
    )
    args = parser.parse_args(argv)
    items = read_items(args.dataset)
    lock = read_lock(args.lock)
    if args.init:
        append_lock(args.lock, {i.id: i.split for i in items if i.id not in lock})
        print(f"pinned {len(items)} items in {args.lock}")
        return 0
    new = assign_new(items, lock)
    append_lock(args.lock, new)
    print(f"assigned {len(new)} new items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
