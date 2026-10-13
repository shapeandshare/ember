"""Load and validate the data-source register and the example-secret list."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .records.example_secret import ExampleSecret
from .records.item import Item
from .records.register_row import RegisterRow
from .records.source_kind import SourceKind
from .records.verdict import Verdict

DATASET_DIR = Path(__file__).resolve().parent
REGISTER_PATH = DATASET_DIR / "register.json"
EXAMPLE_SECRETS_PATH = DATASET_DIR / "example_secrets.json"


def load(path: Path = REGISTER_PATH) -> list[RegisterRow]:
    """Return the register's rows, validated.

    Parameters
    ----------
    path : Path
        The register file.

    Returns
    -------
    list[RegisterRow]
        Every row, in file order.

    Raises
    ------
    ValueError
        If two rows share an ``id``.
    """
    if not path.exists():
        return []
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    rows = [RegisterRow.model_validate(row) for row in data.get("rows", [])]
    ids = [row.id for row in rows]
    if len(ids) != len(set(ids)):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"register has duplicate ids: {duplicates}")
    return rows


def validate(rows: Sequence[RegisterRow], items: Sequence[Item]) -> list[str]:
    """Cross-check the register against the dataset.

    Parameters
    ----------
    rows : Sequence[RegisterRow]
        The register.
    items : Sequence[Item]
        The dataset.

    Returns
    -------
    list[str]
        Problems found; empty when consistent.
    """
    by_id = {row.id: row for row in rows}
    referenced: dict[str, int] = dict.fromkeys(by_id, 0)
    problems: list[str] = []
    for item in items:
        if item.source.kind not in (SourceKind.imported, SourceKind.mined):
            continue
        row_id = item.source.register_row or ""
        row = by_id.get(row_id)
        if row is None:
            problems.append(f"{item.id}: register row {row_id!r} does not exist")
            continue
        if row.verdict is not Verdict.used:
            problems.append(
                f"{item.id}: register row {row_id!r} is {row.verdict.value}"
            )
        referenced[row_id] += 1
    for row in rows:
        if row.items_imported != referenced[row.id]:
            problems.append(
                f"{row.id}: items_imported is {row.items_imported} but "
                f"{referenced[row.id]} items reference it"
            )
    return problems


def validate_example_secrets(entries: Sequence[ExampleSecret]) -> None:
    """Require unique example values.

    Parameters
    ----------
    entries : Sequence[ExampleSecret]
        The example-secret list.

    Raises
    ------
    ValueError
        If two entries share a value.
    """
    values = [entry.value for entry in entries]
    if len(values) != len(set(values)):
        raise ValueError("example secret values must be unique")


def load_example_secrets(path: Path = EXAMPLE_SECRETS_PATH) -> list[ExampleSecret]:
    """Return the example-secret list, validated.

    Parameters
    ----------
    path : Path
        The list file.

    Returns
    -------
    list[ExampleSecret]
        The entries; empty when the file is absent.
    """
    if not path.exists():
        return []
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    entries = [ExampleSecret.model_validate(e) for e in data.get("entries", [])]
    validate_example_secrets(entries)
    return entries
