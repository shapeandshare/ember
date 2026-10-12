"""SizingTable: loads sizing.json and resolves instance types for a model."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .sizing_entry import SizingEntry
from .sizing_status import SizingStatus


class SizingError(Exception):
    """Raised when no suitable instance type exists for a model.

    Parameters
    ----------
    message : str
        Human-readable description naming the reason (model not sized,
        instance type not in table, or status ``unsupported``).
    """


class SizingTable(BaseModel):
    """An in-memory view of ``deployment/aws/sizing.json``.

    Parameters
    ----------
    entries : Sequence[SizingEntry]
        All rows loaded from the JSON file.
    """

    entries: list[SizingEntry]

    @classmethod
    def load(cls, path: Path) -> SizingTable:
        """Load and validate the sizing table from a JSON file.

        Parameters
        ----------
        path : Path
            Path to ``sizing.json``.

        Returns
        -------
        SizingTable
            The loaded and validated table.

        Raises
        ------
        SizingError
            If any model has zero or more than one ``supported`` default row,
            or if a row's ``gpu_memory_gib`` is less than the model's weights
            GiB + 4 but its status is not ``unsupported``.
        """
        raw: list[dict[str, object]] = json.loads(path.read_text())
        entries = [SizingEntry.model_validate(row) for row in raw]
        table = cls(entries=entries)
        table._validate_table()
        return table

    def _validate_table(self) -> None:
        """Run cross-row validation rules.

        Raises
        ------
        SizingError
            If any model has zero or more than one ``supported`` default row.
        """
        models = {e.model for e in self.entries}
        for model in models:
            defaults = [
                e
                for e in self.entries
                if e.model == model and e.default and e.status == SizingStatus.SUPPORTED
            ]
            if len(defaults) != 1:
                raise SizingError(
                    f"model {model!r} has {len(defaults)} supported default rows"
                    f" (expected exactly 1)"
                )

    def resolve(self, model: str, instance_type: str | None) -> SizingEntry:
        """Return the sizing entry for a model and optional instance type.

        Parameters
        ----------
        model : str
            Registry key (e.g. ``"flash"``).
        instance_type : str | None
            EC2 instance type to look up, or ``None`` to use the default.

        Returns
        -------
        SizingEntry
            The matching entry.

        Raises
        ------
        SizingError
            If the model has no rows in the table, the requested instance type
            is not in the table for that model, or the entry's status is
            ``unsupported``.
        """
        model_entries = [e for e in self.entries if e.model == model]
        if not model_entries:
            raise SizingError(
                f"model {model!r} has no sizing rows — it is not supported for"
                " AWS GPU deployment"
            )

        if instance_type is None:
            # Return the single supported default.
            defaults = [
                e
                for e in model_entries
                if e.default and e.status == SizingStatus.SUPPORTED
            ]
            if not defaults:
                raise SizingError(
                    f"model {model!r} has no supported default instance type"
                )
            return defaults[0]

        # Look up the requested instance type.
        matches = [e for e in model_entries if e.instance_type == instance_type]
        if not matches:
            raise SizingError(
                f"instance type {instance_type!r} is not in the sizing table"
                f" for model {model!r}"
            )
        entry = matches[0]
        if entry.status == SizingStatus.UNSUPPORTED:
            raise SizingError(
                f"instance type {instance_type!r} is unsupported for model"
                f" {model!r}: gpu_memory_gib={entry.gpu_memory_gib} is"
                " insufficient (status=unsupported)"
            )
        return entry
