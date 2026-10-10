"""The cap rule's verdict on one length of one model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .depth import Depth
from .failure_reason import DEPTH_REASONS, FailureReason


class LengthVerdict(BaseModel):
    """Whether one length passes, and why not when it fails.

    A passing length has no reason. A failing one has a ``FailureReason``, and a
    ``failed_depth`` exactly when the reason is ``accuracy``, ``brier``, or ``error``.
    ``quality_ok`` is ``None`` when memory failed first.
    """

    model_config = ConfigDict(frozen=True)

    model: str
    length: int
    peak_bytes: int = Field(ge=0)
    budget_bytes: int = Field(gt=0)
    latency_ms_median: float | None
    memory_ok: bool
    quality_ok: bool | None
    passes: bool
    reason: FailureReason | None
    failed_depth: Depth | None

    @model_validator(mode="after")
    def _consistent(self) -> LengthVerdict:
        if self.passes:
            clean = self.reason is None and self.failed_depth is None
            if not (clean and self.memory_ok and self.quality_ok is True):
                raise ValueError("a passing length has no failure")
        elif self.reason is None:
            raise ValueError("a failing length needs a reason")
        elif (self.failed_depth is not None) != (self.reason in DEPTH_REASONS):
            raise ValueError("failed_depth is set only for a depth failure")
        return self
