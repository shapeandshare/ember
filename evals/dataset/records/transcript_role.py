"""TranscriptRole: who spoke a turn in a captured session."""

from __future__ import annotations

from enum import StrEnum


class TranscriptRole(StrEnum):
    """A turn's speaker: the user or the agent."""

    user = "user"
    agent = "agent"
