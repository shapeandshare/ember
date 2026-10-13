"""tag_assignment: items whose gold is a note's own vocabulary tags."""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Final

from ..records.item import Item
from ..records.source import Source
from ..records.source_kind import SourceKind
from ..records.split import Split
from . import ids
from .candidate_note import CandidateNote
from .note_text import note_text
from .selection import RECIPE_SIZE, SEED, select
from .vocabulary import AXES, TagVocabulary

CATEGORY: Final = "tag_assignment"
DISTRACTOR_COUNT: Final = 8
MAX_CANDIDATES: Final = 16


def candidate_tags(
    note: CandidateNote, vocabulary: TagVocabulary, seed: int = SEED
) -> list[str]:
    """Return the sorted candidate tag set: gold plus seeded distractors.

    Distractors prefer the axes the note already carries, then any other
    values; the set never exceeds ``MAX_CANDIDATES`` (FR-010).

    Parameters
    ----------
    note : CandidateNote
        The note.
    vocabulary : TagVocabulary
        The as-read vocabulary.
    seed : int, optional
        The deterministic seed.

    Returns
    -------
    list[str]
        Sorted candidate tags.
    """
    gold = set(note.tags)
    rng = random.Random(f"{seed}:{note.artefact}")  # noqa: S311 - deterministic sampling
    picks: list[str] = []

    def draw(pool: list[str]) -> None:
        rng.shuffle(pool)
        picks.extend(pool[: DISTRACTOR_COUNT - len(picks)])

    for axis in AXES:
        if len(picks) >= DISTRACTOR_COUNT:
            break
        if not any(tag.startswith(f"{axis}/") for tag in gold):
            continue
        draw([tag for tag in vocabulary.values_for(axis) if tag not in gold])
    if len(picks) < DISTRACTOR_COUNT:
        draw(
            [
                tag
                for tag in sorted(vocabulary.descriptions)
                if tag not in gold and tag not in picks
            ]
        )
    return sorted(gold | set(picks))[:MAX_CANDIDATES]


def _question(tag: str, vocabulary: TagVocabulary) -> dict[str, object]:
    description = vocabulary.description_of(tag)
    return {
        "type": "noul",
        "instructions": f"Does this note deserve the tag `{tag}`?",
        "criteria": {
            "true": f"The note calls for `{tag}`: {description}",
            "false": f"The note has no reason to carry `{tag}`",
        },
    }


def build_item(
    note: CandidateNote,
    vocabulary: TagVocabulary,
    *,
    commit: str,
    register_row: str,
    split: Split = Split.dev,
) -> Item:
    """Build one ``tag_assignment`` item from a candidate note.

    The state carries the note's title and body (frontmatter stripped, the
    body's H1 removed when it repeats the title) followed by the full as-read
    vocabulary (FR-017). Every candidate tag becomes one ``noul`` question
    whose gold is 1 exactly for the note's own tags.

    Parameters
    ----------
    note : CandidateNote
        The note.
    vocabulary : TagVocabulary
        The as-read vocabulary.
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
    tags = candidate_tags(note, vocabulary)
    gold = set(note.tags)
    state = f"{note_text(note)}\n\n{vocabulary.as_state_block()}"
    return Item(
        id=ids.item_id(CATEGORY, note.artefact),
        category=CATEGORY,
        split=split,
        state=state,
        questions={tag: _question(tag, vocabulary) for tag in tags},
        gold_labels={tag: tag in gold for tag in tags},
        rationale=(
            f"Mined from {note.artefact} at {commit}; "
            "gold is the note's own vocabulary tags."
        ),
        source=Source(
            kind=SourceKind.mined,
            artefact=note.artefact,
            commit=commit,
            register_row=register_row,
        ),
    )


def build_items(
    candidates: Sequence[CandidateNote],
    vocabulary: TagVocabulary,
    *,
    commit: str,
    register_row: str,
    count: int | None = None,
) -> list[Item]:
    """Build the recipe's items: seeded selection, one item per note."""
    target = RECIPE_SIZE if count is None else count
    return [
        build_item(note, vocabulary, commit=commit, register_row=register_row)
        for note in select(candidates, count=target)
    ]
