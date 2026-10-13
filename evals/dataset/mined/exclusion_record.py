"""ExclusionRecord: one note's declared exclusion."""

from __future__ import annotations

from dataclasses import dataclass

from .exclusion_reason import ExclusionReason


@dataclass(frozen=True, slots=True)
class ExclusionRecord:
    """A note that was excluded, with its declared reason.

    Parameters
    ----------
    artefact : str
        The vault-relative path of the excluded note.
    reason : ExclusionReason
        The declared reason.
    """

    artefact: str
    reason: ExclusionReason
