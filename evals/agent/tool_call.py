"""One completed (or failed) tool call recorded during an agent session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """One completed (or failed) tool call, in the order it finished."""

    index: int
    name: str
    input: dict[str, Any]
    output: str
    status: str
    per_call_ms: float | None = None
