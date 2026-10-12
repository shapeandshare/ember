"""Deterministic, seeded selection of the notes a recipe mines."""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence
from typing import Final

from .candidate_note import CandidateNote

SEED: Final = 20261012
RECIPE_SIZE: Final = 65


def select(
    candidates: Sequence[CandidateNote],
    count: int = RECIPE_SIZE,
    seed: int = SEED,
) -> list[CandidateNote]:
    """Pick ``count`` notes, seeded and spread across type groups.

    Candidates are grouped by ``type``, each group is shuffled with the
    fixed seed, and the groups are interleaved round-robin, so a pick spans
    several ``type/*`` values without declaring per-type quotas. The same
    candidates, count, and seed always yield the same pick.

    Parameters
    ----------
    candidates : Sequence[CandidateNote]
        The notes that passed the exclusion rules.
    count : int, optional
        How many notes to pick.
    seed : int, optional
        The deterministic seed.

    Returns
    -------
    list[CandidateNote]
        The picked notes, fewer when the pool is smaller than ``count``.
    """
    groups: dict[str, list[CandidateNote]] = defaultdict(list)
    for note in sorted(candidates, key=lambda item: item.artefact):
        groups[note.type].append(note)
    rng = random.Random(seed)
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
                if len(picked) == count:
                    return picked
    return picked
