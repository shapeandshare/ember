"""note_placement: items whose gold is the folder a note actually lives in."""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence
from typing import Final

from ..records.item import Item
from ..records.source import Source
from ..records.source_kind import SourceKind
from ..records.split import Split
from . import ids
from .candidate_note import CandidateNote
from .note_text import note_text
from .selection import SEED
from .vocabulary import TagVocabulary

CATEGORY: Final = "note_placement"
PLACEMENT_SIZE: Final = 30
QUESTION_ID: Final = "placement"


def placement_of(artefact: str) -> str:
    """Return the folder a vault artefact lives in."""
    return artefact.split("/", 1)[0]


def placements_for(candidates: Sequence[CandidateNote]) -> list[str]:
    """Return the sorted folder choices the candidate pool actually uses."""
    return sorted({placement_of(note.artefact) for note in candidates})


def _question(placements: Sequence[str]) -> dict[str, object]:
    return {
        "type": "choice",
        "instructions": "Which folder does this vault note belong in?",
        "criteria": {
            folder: f"Place the note under {folder}/" for folder in placements
        },
    }


def pick(
    candidates: Sequence[CandidateNote], count: int | None = None
) -> list[CandidateNote]:
    """Pick notes spread across their actual folders (deterministic, seeded)."""
    target = PLACEMENT_SIZE if count is None else count
    groups: dict[str, list[CandidateNote]] = defaultdict(list)
    for note in sorted(candidates, key=lambda item: item.artefact):
        groups[placement_of(note.artefact)].append(note)
    rng = random.Random(SEED)  # noqa: S311 - deterministic sampling
    for group in groups.values():
        rng.shuffle(group)
    keys = sorted(groups)
    deepest = max((len(groups[key]) for key in keys), default=0)
    picked: list[CandidateNote] = []
    for index in range(deepest):
        for key in keys:
            group = groups[key]
            if index < len(group):
                picked.append(group[index])
                if len(picked) == target:
                    return picked
    return picked


def build_items(
    candidates: Sequence[CandidateNote],
    vocabulary: TagVocabulary,
    *,
    commit: str,
    register_row: str,
    count: int | None = None,
) -> list[Item]:
    """Build the recipe's items: a folder-spread pick, one item per note."""
    placements = placements_for(candidates)
    return [
        build_item(note, placements, commit=commit, register_row=register_row)
        for note in pick(candidates, count)
    ]


def build_item(
    note: CandidateNote,
    placements: Sequence[str],
    *,
    commit: str,
    register_row: str,
    split: Split = Split.dev,
) -> Item:
    """Build one item; the gold is the note's actual folder.

    Parameters
    ----------
    note : CandidateNote
        The note.
    placements : Sequence[str]
        The folder choices (the question set is fixed for the whole mine).
    commit : str
        The pinned source commit (40-hex).
    register_row : str
        The register row id for the source.
    split : Split, optional
        The provisional split; the miner re-pins it from the lock.

    Returns
    -------
    Item
        The dataset item.
    """
    placement = placement_of(note.artefact)
    return Item(
        id=ids.item_id(CATEGORY, note.artefact),
        category=CATEGORY,
        split=split,
        state=note_text(note),
        questions={QUESTION_ID: _question(placements)},
        gold_labels={QUESTION_ID: placement},
        rationale=(
            f"Mined from {note.artefact} at {commit}; gold is its actual folder."
        ),
        source=Source(
            kind=SourceKind.mined,
            artefact=note.artefact,
            commit=commit,
            register_row=register_row,
        ),
    )
