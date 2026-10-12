"""TranscriptTurn: one speaker's turn in a captured session."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .transcript_role import TranscriptRole


class TranscriptTurn(BaseModel):
    """One turn of the source session.

    Parameters
    ----------
    role : TranscriptRole
        Who spoke: the user or the agent.
    content : str
        The turn's text, already redacted.
    """

    role: TranscriptRole
    content: str = Field(min_length=1)
