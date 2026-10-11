"""Content hashes: the dataset version, per-recipe hashes, and provenance hashes.

The *scoring projection* of an item is exactly what the model is scored on;
annotations (source, rationale, kind, tier, review fields) never enter a hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .io import DATASET_PATH, read_items
from .records.item import Item
from .register import REGISTER_PATH

PROJECTED = ("id", "category", "split", "state", "images", "videos", "media_kwargs")
PROJECTED_REQUIRED = ("questions", "gold_labels")


def projection(item: Item | Mapping[str, Any]) -> dict[str, Any]:
    """Return the scored fields of ``item`` and nothing else.

    Parameters
    ----------
    item : Item | Mapping[str, Any]
        A validated item or a raw dataset record.

    Returns
    -------
    dict[str, Any]
        ``id``, ``category``, ``split``, ``state``, any media fields present,
        ``questions``, and ``gold_labels``.
    """
    record = item.model_dump(mode="json") if isinstance(item, Item) else dict(item)
    projected = {key: record[key] for key in PROJECTED if record.get(key) is not None}
    for key in PROJECTED_REQUIRED:
        projected[key] = record[key]
    return projected


def _canonical(items: Iterable[Item | Mapping[str, Any]]) -> str:
    projections = sorted((projection(i) for i in items), key=lambda p: str(p["id"]))
    return "\n".join(
        json.dumps(p, sort_keys=True, ensure_ascii=False) for p in projections
    )


def dataset_content_sha256(items: Iterable[Item | Mapping[str, Any]]) -> str:
    """Return the dataset version: SHA-256 over every item's scoring projection."""
    return hashlib.sha256(_canonical(items).encode("utf-8")).hexdigest()


def recipe_sha256(items: Iterable[Item | Mapping[str, Any]]) -> str:
    """Return the SHA-256 over one recipe's scoring projections."""
    return dataset_content_sha256(items)


def recipe_hashes(items: Sequence[Item | Mapping[str, Any]]) -> dict[str, str]:
    """Return ``{category: recipe_sha256}`` for every recipe in ``items``."""
    grouped: dict[str, list[Item | Mapping[str, Any]]] = defaultdict(list)
    for item in items:
        category = item.category if isinstance(item, Item) else str(item["category"])
        grouped[category].append(item)
    return {category: recipe_sha256(rows) for category, rows in sorted(grouped.items())}


def dataset_sha256(path: Path) -> str:
    """Return the SHA-256 of the dataset file's bytes (provenance, not the version)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register_sha256(path: Path) -> str:
    """Return the SHA-256 of the data-source register file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(dataset_path: Path, register_path: Path) -> dict[str, Any]:
    """Return every hash a run records, computed from the files on disk."""
    items = read_items(dataset_path)
    return {
        "dataset_content_sha256": dataset_content_sha256(items),
        "dataset_sha256": dataset_sha256(dataset_path),
        "recipe_sha256": recipe_hashes(items),
        "register_sha256": register_sha256(register_path)
        if register_path.exists()
        else None,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Print the dataset's hashes (``ember eval dataset hash``)."""
    parser = argparse.ArgumentParser(prog="ember eval dataset hash")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    hashes = summary(args.dataset, REGISTER_PATH)
    if args.as_json:
        print(json.dumps(hashes, indent=2))
    else:
        print(f"content   {hashes['dataset_content_sha256']}")
        print(f"file      {hashes['dataset_sha256']}")
        for category, digest in hashes["recipe_sha256"].items():
            print(f"recipe    {category:<20} {digest}")
        print(f"register  {hashes['register_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
