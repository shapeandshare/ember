"""Read and write the benchmark dataset as validated ``Item`` records."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..atomic import write_atomic
from .records.item import Item
from .records.source import from_legacy

EVALS_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = EVALS_DIR / "clef-flash.jsonl"


def read_raw(path: Path) -> list[dict[str, Any]]:
    """Return the dataset's lines as plain dicts, in file order.

    Parameters
    ----------
    path : Path
        The JSONL file.

    Returns
    -------
    list[dict[str, Any]]
        One dict per non-blank line.
    """
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record: dict[str, Any] = json.loads(line)
            records.append(record)
    return records


def to_item(
    record: dict[str, Any], *, legacy_dataset_version: str | None = None
) -> Item:
    """Validate one raw record, mapping a legacy string ``source`` when allowed.

    Parameters
    ----------
    record : dict[str, Any]
        One dataset line.
    legacy_dataset_version : str | None
        The content hash to record on items whose ``source`` is still a
        pre-Phase-0 string; ``None`` rejects such items.

    Returns
    -------
    Item
        The validated item.

    Raises
    ------
    ValueError
        If ``source`` is a string and no legacy version was given.
    """
    source = record.get("source")
    if isinstance(source, str):
        if legacy_dataset_version is None:
            raise ValueError(
                f"{record.get('id')}: legacy string source {source!r}; pass "
                "legacy_dataset_version to read a pre-Phase-0 dataset"
            )
        record = {**record, "source": from_legacy(source, legacy_dataset_version)}
    return Item.model_validate(record)


def read_items(path: Path, *, legacy_dataset_version: str | None = None) -> list[Item]:
    """Read and validate every item in ``path``.

    Parameters
    ----------
    path : Path
        The JSONL file.
    legacy_dataset_version : str | None
        See ``to_item``.

    Returns
    -------
    list[Item]
        The items in file order.
    """
    return [
        to_item(record, legacy_dataset_version=legacy_dataset_version)
        for record in read_raw(path)
    ]


def dump_item(item: Item) -> str:
    """Return one JSONL line for ``item`` (no nulls, UTF-8 preserved)."""
    return json.dumps(
        item.model_dump(
            mode="json", exclude_none=True, exclude_defaults=True, by_alias=True
        ),
        ensure_ascii=False,
    )


def write_items(path: Path, items: Sequence[Item]) -> None:
    """Write ``items`` to ``path`` atomically, one JSON line each, in order.

    Parameters
    ----------
    path : Path
        The destination JSONL file.
    items : Sequence[Item]
        The items to write.
    """
    write_atomic(path, "".join(dump_item(item) + "\n" for item in items))
