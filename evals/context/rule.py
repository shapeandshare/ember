"""The pre-declared cap rule (FR-010, research R12), a pure function of the summary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .records.cell_result import CellResult
from .records.depth import Depth
from .records.failure_reason import FailureReason
from .records.length_verdict import LengthVerdict
from .records.model_verdict import ModelVerdict

_DECIMALS = 6


@dataclass(frozen=True)
class LengthMemory:
    """What a length cost: peak bytes, whether it ran out of memory, latency."""

    peak_bytes: int
    oom: bool
    latency_ms_median: float | None


def _quality_failure(
    cells: Mapping[Depth, CellResult],
    baseline: Mapping[Depth, CellResult],
    depths: Sequence[Depth],
    tolerance_accuracy: float,
    tolerance_brier: float,
) -> tuple[FailureReason, Depth] | None:
    for depth in depths:
        cell, base = cells.get(depth), baseline.get(depth)
        if cell is None or base is None:
            # Nothing measured at this depth: the length can't be shown to pass.
            return FailureReason.ACCURACY, depth
        if cell.exploratory:
            # A subset cell compares with 2K on the same items: its paired delta.
            drop, rise = cell.delta_accuracy, cell.delta_brier
        else:
            drop, rise = cell.accuracy - base.accuracy, cell.brier - base.brier
        if round(drop, _DECIMALS) < -tolerance_accuracy:
            return FailureReason.ACCURACY, depth
        if round(rise, _DECIMALS) > tolerance_brier:
            return FailureReason.BRIER, depth
    return None


def evaluate(
    cells: Sequence[CellResult],
    memory: Mapping[int, LengthMemory],
    *,
    model: str,
    tolerance_accuracy: float,
    tolerance_brier: float,
    budget_bytes: int,
    depths: Sequence[Depth] = tuple(Depth),
) -> tuple[list[LengthVerdict], ModelVerdict]:
    """Judge every measured length and pick the model's cap.

    A length passes when its peak fits the budget and, at every depth, accuracy
    is at least the 2K accuracy minus ``tolerance_accuracy`` and Brier at most
    the 2K Brier plus ``tolerance_brier``. A memory failure or OOM fails that
    length and every longer one. The cap is the longest length that passes along
    with every shorter one, or ``None``.

    Returns
    -------
    tuple[list[LengthVerdict], ModelVerdict]
        One verdict per length in ``memory``, ascending, and the model verdict.
    """
    by_length: dict[int, dict[Depth, CellResult]] = {}
    for cell in cells:
        by_length.setdefault(cell.length, {})[cell.depth] = cell
    lengths = sorted(memory)
    baseline = by_length.get(lengths[0], {}) if lengths else {}
    verdicts: list[LengthVerdict] = []
    memory_failure: FailureReason | None = None
    for length in lengths:
        measured = memory[length]
        if memory_failure is None and measured.oom:
            memory_failure = FailureReason.OOM
        elif memory_failure is None and measured.peak_bytes > budget_bytes:
            memory_failure = FailureReason.MEMORY
        failure = (
            None
            if memory_failure is not None
            else _quality_failure(
                by_length.get(length, {}),
                baseline,
                depths,
                tolerance_accuracy,
                tolerance_brier,
            )
        )
        verdicts.append(
            LengthVerdict(
                model=model,
                length=length,
                peak_bytes=measured.peak_bytes,
                budget_bytes=budget_bytes,
                latency_ms_median=measured.latency_ms_median,
                memory_ok=memory_failure is None,
                quality_ok=None if memory_failure else failure is None,
                passes=memory_failure is None and failure is None,
                reason=memory_failure or (failure[0] if failure else None),
                failed_depth=failure[1] if failure else None,
            )
        )
    cap: int | None = None
    first: LengthVerdict | None = None
    for verdict in verdicts:
        if not verdict.passes:
            first = verdict
            break
        cap = verdict.length
    return verdicts, ModelVerdict(
        model=model,
        cap=cap,
        first_failure_length=first.length if first else None,
        first_failure_reason=first.reason if first else None,
        first_failure_depth=first.failed_depth if first else None,
    )
