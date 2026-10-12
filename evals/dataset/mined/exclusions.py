"""The declared selection rules: which vault notes the miner may consider.

Rules apply in a fixed order and every excluded note is recorded with its
reason (specs/007 FR-014); nothing is guessed and nothing is silently
dropped. ``_meta/`` is not note space and is skipped by the caller.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from ..secret_guard import SECRET_PATTERNS
from .candidate_note import CandidateNote
from .exclusion_reason import ExclusionReason
from .exclusion_record import ExclusionRecord
from .vocabulary import TagVocabulary

NON_CONTENT_NAMES: Final = frozenset({"index.md", "README.md"})
WORD_FLOOR: Final = 80
MAX_GOLD: Final = 8


def _has_secret(note: CandidateNote) -> bool:
    text = f"{note.title}\n{note.body}"
    return any(pattern.search(text) for pattern in SECRET_PATTERNS.values())


def classify(note: CandidateNote, vocabulary: TagVocabulary) -> ExclusionRecord | None:
    """Classify one vault note against the declared exclusion rules.

    The order is fixed: navigation and governance shapes first, then the
    out-of-scope type, then content shape and tag-set bounds, then drift,
    then the credential screen. The first matching rule decides, so every
    excluded note carries exactly one reason.

    Parameters
    ----------
    note : CandidateNote
        The note to classify.
    vocabulary : TagVocabulary
        The as-read controlled vocabulary.

    Returns
    -------
    ExclusionRecord | None
        The exclusion, or ``None`` when the note is a candidate.
    """
    if Path(note.artefact).name in NON_CONTENT_NAMES or note.type == "moc":
        return ExclusionRecord(note.artefact, ExclusionReason.non_content)
    if note.type == "spec":
        return ExclusionRecord(note.artefact, ExclusionReason.out_of_scope)
    if len(note.body.split()) < WORD_FLOOR:
        return ExclusionRecord(note.artefact, ExclusionReason.non_content)
    if not note.tags or len(note.tags) > MAX_GOLD:
        return ExclusionRecord(note.artefact, ExclusionReason.tag_set_bounds)
    if any(not vocabulary.contains(tag) for tag in note.tags):
        return ExclusionRecord(note.artefact, ExclusionReason.drift)
    if _has_secret(note):
        return ExclusionRecord(note.artefact, ExclusionReason.secret)
    return None
