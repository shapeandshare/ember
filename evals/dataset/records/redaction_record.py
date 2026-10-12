"""RedactionRecord: the redaction provenance that makes a capture admissible."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RedactionRecord(BaseModel):
    """The redaction record a captured session must carry.

    Parameters
    ----------
    session_id : str
        Must equal the transcript's ``session_id``.
    redaction_sha256 : str
        The 64-hex hash copied onto ``Source.redaction_sha256``.
    method : str
        How redaction was performed (documented, never a credential).
    redacted_on : str
        ISO date the redaction was done.
    """

    session_id: str = Field(min_length=1)
    redaction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    method: str = Field(min_length=1)
    redacted_on: str = Field(min_length=1)
