"""The probe summary: ``summary.json``, derived from the rows and the manifest."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from .cell_result import CellResult
from .length_verdict import LengthVerdict
from .model_verdict import ModelVerdict


class ProbeSummary(BaseModel):
    """Cells, per-length verdicts, and per-model caps for one run.

    ``rule`` copies the manifest's tolerances, budgets, and lengths;
    ``inputs_sha256`` digests the rows files and the manifest.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str
    canonical: bool
    rule: dict[str, Any]
    cells: list[CellResult]
    lengths: list[LengthVerdict]
    verdicts: list[ModelVerdict]
    inputs_sha256: dict[str, str]
