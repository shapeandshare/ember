"""CandidateNote: one vault note that passed the exclusion rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandidateNote:
    """A vault note eligible for mining.

    Parameters
    ----------
    artefact : str
        The vault-relative path (the item's artefact).
    title : str
        The note's title.
    type : str
        The note's type value (the ``type/*`` axis).
    tags : tuple[str, ...]
        The note's controlled tags.
    body : str
        The note body, frontmatter stripped.
    """

    artefact: str
    title: str
    type: str
    tags: tuple[str, ...]
    body: str
