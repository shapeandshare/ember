"""The cap rule's verdict on one model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from .depth import Depth
from .failure_reason import QUALITY_REASONS, FailureReason


class ModelVerdict(BaseModel):
    """A model's cap and its first failing length.

    ``cap`` is the longest length that passes along with every shorter one, or
    ``None`` when none does. The failure fields are ``None`` when nothing
    failed; ``first_failure_depth`` is set only for an accuracy or brier failure.
    """

    model_config = ConfigDict(frozen=True)

    model: str
    cap: int | None
    first_failure_length: int | None
    first_failure_reason: FailureReason | None
    first_failure_depth: Depth | None

    @model_validator(mode="after")
    def _consistent(self) -> ModelVerdict:
        if self.first_failure_length is None:
            if self.first_failure_reason is not None or self.first_failure_depth:
                raise ValueError("no failure means no failure reason or depth")
        elif self.first_failure_reason is None:
            raise ValueError("a failure needs a reason")
        elif (self.first_failure_depth is not None) != (
            self.first_failure_reason in QUALITY_REASONS
        ):
            raise ValueError("first_failure_depth is set only for a quality failure")
        return self
