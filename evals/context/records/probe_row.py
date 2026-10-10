"""One probe inference: a line of ``rows-<model>.jsonl``."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .depth import Depth
from .probe_manifest import LENGTH_TOLERANCE
from .row_status import RowStatus


class ProbeRow(BaseModel):
    """One inference at one (model, item, length, depth), unique within a run.

    The token parts sum to the total; an ``ok`` row's total lies within
    ``LENGTH_TOLERANCE`` tokens below its length; only an ``ok`` row carries
    answers; and ``peak_bytes = rss_start_bytes + driver_peak_bytes``.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str
    model: str
    item_id: str
    split: str
    category: str
    length: int
    depth: Depth
    total_tokens: int = Field(ge=0)
    state_tokens: int = Field(ge=0)
    media_tokens: int = Field(ge=0)
    fixed_tokens: int = Field(ge=0)
    answers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    latency_ms: float = Field(ge=0)
    rss_start_bytes: int = Field(ge=0)
    driver_peak_bytes: int = Field(ge=0)
    peak_bytes: int = Field(ge=0)
    status: RowStatus
    exploratory: bool = False
    error: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> ProbeRow:
        parts = self.state_tokens + self.media_tokens + self.fixed_tokens
        if parts != self.total_tokens:
            raise ValueError("token parts must sum to the total")
        in_range = self.length - LENGTH_TOLERANCE <= self.total_tokens <= self.length
        if self.status is RowStatus.OK and not in_range:
            raise ValueError("an ok row's total must be within the length tolerance")
        if self.status is not RowStatus.OK and self.answers:
            raise ValueError("only an ok row carries answers")
        if self.peak_bytes != self.rss_start_bytes + self.driver_peak_bytes:
            raise ValueError(
                "peak_bytes must equal rss_start_bytes + driver_peak_bytes"
            )
        return self

    @property
    def key(self) -> tuple[str, str, int, Depth]:
        """The row's identity within a run: (model, item, length, depth)."""
        return (self.model, self.item_id, self.length, self.depth)
