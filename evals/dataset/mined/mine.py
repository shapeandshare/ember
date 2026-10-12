"""Mine a pinned vault snapshot into benchmark items (composition root)."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from ...atomic import write_atomic
from ..io import DATASET_PATH, read_items, write_items
from ..splitting import LOCK_PATH, append_lock, assign_new, read_lock
from .candidate_note import CandidateNote
from .exclusions import MAX_GOLD, WORD_FLOOR, classify
from .frontmatter import body_of, parse
from .mine_error import MineError
from .mine_summary import MineSummary
from .sampling_manifest import SamplingManifest
from .selection import RECIPE_SIZE, SEED, select
from .snapshot import VaultSnapshot, VaultSnapshotError
from .snapshot_file import SnapshotFile
from .tag_assignment import (
    CATEGORY as TAG_ASSIGNMENT,
    DISTRACTOR_COUNT,
    MAX_CANDIDATES,
    build_item,
)
from .vocabulary import TagVocabulary

DEFAULT_SOURCE: Final = Path(__file__).resolve().parents[3].parent / "oldgrowth"
OLDGROWTH_PIN: Final = "692f4bb58b7f62105aeb73fba8dfee12bfdecd53"
OLDGROWTH_REGISTER_ROW: Final = "oldgrowth-vault"
MANIFEST_DIRNAME: Final = "mined"
GRANT_FILE: Final = "LICENSES.md"
GRANT_MARKER: Final = "ember benchmark reproduction"


def _require_grant(source_dir: Path) -> None:
    """Refuse when the repository's committed ``LICENSES.md`` records no grant.

    Parameters
    ----------
    source_dir : Path
        The source repository checkout.

    Raises
    ------
    MineError
        When the grant marker is absent (FR-012).
    """
    try:
        text = VaultSnapshot(source_dir, "HEAD").read_file(GRANT_FILE)
    except VaultSnapshotError:
        text = ""
    if GRANT_MARKER not in text:
        raise MineError(
            f"{GRANT_FILE} in {source_dir} records no written permission for mining "
            f"(missing {GRANT_MARKER!r}); the copyright holder's grant is required."
        )


def _note_from(entry: SnapshotFile) -> CandidateNote:
    meta = parse(entry.text)
    return CandidateNote(
        artefact=entry.path,
        title=meta.title,
        type=meta.type,
        tags=tuple(meta.tags),
        body=body_of(entry.text),
    )


def mine(
    *,
    source_dir: Path = DEFAULT_SOURCE,
    commit: str = OLDGROWTH_PIN,
    register_row: str = OLDGROWTH_REGISTER_ROW,
    recipe: str = TAG_ASSIGNMENT,
    dataset_path: Path = DATASET_PATH,
    lock_path: Path = LOCK_PATH,
    count: int = RECIPE_SIZE,
) -> MineSummary:
    """Mine one recipe's items and write the dataset, lock, and manifest.

    Idempotent: the same snapshot, seed, and count produce identical bytes.
    Items replace their earlier selves in place; new ids are appended and
    pinned in the splits lock. The register and the card are untouched.

    Parameters
    ----------
    source_dir : Path, optional
        The source repository checkout.
    commit : str, optional
        The pinned commit.
    register_row : str, optional
        The register row id for the source.
    recipe : str, optional
        The recipe to mine.
    dataset_path : Path, optional
        The dataset JSONL to update.
    lock_path : Path, optional
        The splits lock to extend.
    count : int, optional
        How many notes to pick.

    Returns
    -------
    MineSummary
        Items written, candidates, and exclusion counts.
    """
    snapshot = VaultSnapshot(source_dir, commit).require()
    _require_grant(source_dir)
    vocabulary = TagVocabulary.from_tags_md(snapshot.read("_meta/tags.md"))
    exclusions = []
    candidates: list[CandidateNote] = []
    for entry in snapshot.files():
        if entry.path.startswith("_meta/"):
            continue
        note = _note_from(entry)
        record = classify(note, vocabulary)
        if record is None:
            candidates.append(note)
        else:
            exclusions.append(record)
    picked = select(candidates, count=count)
    built = [
        build_item(note, vocabulary, commit=commit, register_row=register_row)
        for note in picked
    ]
    existing = read_items(dataset_path) if dataset_path.exists() else []
    lock = read_lock(lock_path)
    built_ids = {item.id for item in built}
    sequenced = [item for item in existing if item.id not in built_ids] + built
    assignments = assign_new(sequenced, lock)
    resolved = assignments | lock
    built = [
        item.model_copy(update={"split": resolved[item.id]}) for item in built
    ]
    merged = list(existing)
    positions = {item.id: index for index, item in enumerate(merged)}
    for item in built:
        if item.id in positions:
            merged[positions[item.id]] = item
        else:
            merged.append(item)
    write_items(dataset_path, merged)
    append_lock(lock_path, assignments)
    counts = Counter(record.reason.value for record in exclusions)
    manifest = SamplingManifest(
        recipe=recipe,
        source_commit=commit,
        register_row=register_row,
        seed=SEED,
        count=count,
        word_floor=WORD_FLOOR,
        max_gold=MAX_GOLD,
        distractor_count=DISTRACTOR_COUNT,
        max_candidates=MAX_CANDIDATES,
        exclusions=exclusions,
        item_ids=[item.id for item in built],
    )
    manifest_path = dataset_path.parent / MANIFEST_DIRNAME / f"{recipe}.json"
    write_atomic(manifest_path, manifest.model_dump_json(indent=2) + "\n")
    return MineSummary(
        recipe=recipe,
        source_commit=commit,
        items_written=len(built),
        candidates=len(candidates),
        exclusions=dict(sorted(counts.items())),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the miner (``ember eval mine``)."""
    parser = argparse.ArgumentParser(prog="ember eval mine")
    parser.add_argument("--recipe", default=TAG_ASSIGNMENT)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    parser.add_argument("--count", type=int, default=RECIPE_SIZE)
    args = parser.parse_args(argv)
    if args.recipe != TAG_ASSIGNMENT:
        parser.error(f"unknown recipe {args.recipe!r}; known: {TAG_ASSIGNMENT}")
    summary = mine(
        source_dir=args.source_dir,
        recipe=args.recipe,
        dataset_path=args.dataset,
        lock_path=args.lock,
        count=args.count,
    )
    print(f"mined {summary.items_written} items from {summary.source_commit[:12]}")
    print(f"candidates {summary.candidates}; exclusions {summary.exclusions}")
    return 0
