"""The probe manifest: pinned inputs and rule parameters, written before inference."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .depth import Depth
from .probe_model import ProbeModel

#: The form of a generated run id.
RUN_ID_PATTERN = re.compile(r"^context_\d{8}T\d{6}Z$")
#: A ``--run-id`` value must be a safe directory name.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

LENGTHS = (2048, 4096, 8192, 16384, 24576, 32768, 65536)
BASELINE_LENGTH = 2048
LENGTH_TOLERANCE = 32
TOLERANCE_ACCURACY = 0.02
TOLERANCE_BRIER = 0.02
BOOTSTRAP_RESAMPLES = 10000
BOOTSTRAP_LEVEL = 0.95
SEED = 0
EXPLORATORY_ITEMS = 48

_FIXED = {
    "length_tolerance_tokens": LENGTH_TOLERANCE,
    "tolerance_accuracy": TOLERANCE_ACCURACY,
    "tolerance_brier": TOLERANCE_BRIER,
    "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
    "bootstrap_level": BOOTSTRAP_LEVEL,
    "seed": SEED,
}


def new_run_id(now: datetime | None = None) -> str:
    """Return a run id of the form ``context_<UTC %Y%m%dT%H%M%SZ>``."""
    return f"context_{(now or datetime.now(UTC)).strftime('%Y%m%dT%H%M%SZ')}"


class ProbeManifest(BaseModel):
    """A probe run's pinned inputs and pre-declared rule (data-model.md).

    The rule parameters are fixed: a manifest that changes one is invalid.
    ``run_id`` is generated as ``context_<UTC timestamp>`` or given by
    ``--run-id``; either way it must be a safe directory name.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str
    created_at: str
    canonical: bool
    git_hash: str
    git_dirty: bool
    ember_version: str
    host: dict[str, Any]
    device: str
    dtype: str
    models: dict[str, ProbeModel]
    dataset_path: str
    dataset_sha256: str
    item_ids: list[str]
    excluded: dict[str, str]
    filler_path: str
    filler_sha256: str
    filler_source: str
    filler_licence: str
    lengths: list[int]
    depths: list[Depth] = Field(default_factory=lambda: list(Depth))
    length_tolerance_tokens: int = LENGTH_TOLERANCE
    tolerance_accuracy: float = TOLERANCE_ACCURACY
    tolerance_brier: float = TOLERANCE_BRIER
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES
    bootstrap_level: float = BOOTSTRAP_LEVEL
    seed: int = SEED
    exploratory_items: int
    exploratory_item_ids: list[str]
    pilot_projected_half_width: float | None = None
    sizing_passed: bool | None = None

    @field_validator("run_id")
    @classmethod
    def _safe_run_id(cls, value: str) -> str:
        if not _SAFE_NAME.fullmatch(value):
            raise ValueError(f"run id {value!r} is not a safe directory name")
        return value

    @field_validator("lengths")
    @classmethod
    def _ascending_from_baseline(cls, value: list[int]) -> list[int]:
        ascending = all(b > a for a, b in pairwise(value))
        if not value or value[0] != BASELINE_LENGTH or not ascending:
            raise ValueError(f"lengths must ascend from {BASELINE_LENGTH}")
        return value

    @field_validator("depths")
    @classmethod
    def _distinct_depths(cls, value: list[Depth]) -> list[Depth]:
        if not value or len(set(value)) != len(value):
            raise ValueError("depths must be distinct and non-empty")
        return value

    @model_validator(mode="after")
    def _fixed_rule_and_subset(self) -> ProbeManifest:
        for name, expected in _FIXED.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} is fixed at {expected}")
        if self.exploratory_items != min(EXPLORATORY_ITEMS, len(self.item_ids)):
            raise ValueError(f"exploratory_items is {EXPLORATORY_ITEMS}, or every item")
        chosen = self.exploratory_item_ids
        if (
            len(chosen) != self.exploratory_items
            or len(set(chosen)) != len(chosen)
            or not set(chosen) <= set(self.item_ids)
        ):
            raise ValueError("exploratory_item_ids must be drawn from item_ids")
        return self
