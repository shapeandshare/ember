"""CaptureOutcome: how a session capture ended."""

from __future__ import annotations

from enum import StrEnum


class CaptureOutcome(StrEnum):
    """The result of converting a session into a candidate item.

    Attributes
    ----------
    converted : str
        The session became a schema-valid candidate.
    refused_no_redaction : str
        The redaction record was missing or did not match the session.
    refused_live_secret : str
        A credential survived; the ``no-live-secret`` rule is never relaxed.
    """

    converted = "converted"
    refused_no_redaction = "refused_no_redaction"
    refused_live_secret = "refused_live_secret"
