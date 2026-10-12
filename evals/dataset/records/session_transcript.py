"""SessionTranscript: the capture input for one consented, redacted session."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .transcript_turn import TranscriptTurn


class SessionTranscript(BaseModel):
    """A real session, ready to become a candidate item.

    Parameters
    ----------
    session_id : str
        Identifies the source session (``Source.session_id``).
    category : str
        The recipe the captured item will belong to.
    question_id : str
        The question within that recipe the session answers.
    question : dict[str, Any]
        The typed question, as the recipe uses it (``type`` and ``criteria``).
    turns : list[TranscriptTurn]
        The session's turns, already redacted.
    reviewed_choice : str
        The choice endorsed on review — this becomes gold.
    acted_choice : str
        The choice made in the moment (kept as a secondary annotation).
    """

    session_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    question: dict[str, Any]
    turns: list[TranscriptTurn] = Field(min_length=1)
    reviewed_choice: str = Field(min_length=1)
    acted_choice: str = Field(min_length=1)
