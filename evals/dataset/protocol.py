"""The labelling protocol and the record of dataset versions (FR-046).

``RULES`` are the protocol sentences the report prints, each carrying the
dataset version (content hash) it first applies to. ``versions.lock`` is the
append-only record of every dataset version ever published: ``check`` fails
when the current dataset's content hash is not recorded, or when a rule or a
scale names a version that never existed. ``ember eval dataset card`` records
the current version when it regenerates the card.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..atomic import write_atomic
from .records.protocol_rule import ProtocolRule

DATASET_DIR = Path(__file__).resolve().parent
VERSIONS_PATH = DATASET_DIR / "versions.lock"

# Phase 0 (specs/004) is the first version any rule is recorded against; the
# rules that predate it apply from this version because nothing earlier was
# versioned by content.
FOUNDATIONS_VERSION = "1e1bb88d47f0833b55e0195357dab30586c2a7a9b5c3d58524cbe48c622cc367"

RULES: tuple[ProtocolRule, ...] = (
    ProtocolRule(
        text="Labels were judged from `state` and the option descriptions alone, "
        "and were fixed before any model run.",
        since=FOUNDATIONS_VERSION,
    ),
    ProtocolRule(
        text="`needs_review` is true exactly when `risk` is Medium or High, and "
        "`retry` is true only for `flaky` failures.",
        since=FOUNDATIONS_VERSION,
    ),
    ProtocolRule(
        text="Drafts whose evidence fit two options were rewritten or dropped while "
        "authoring, before any run.",
        since=FOUNDATIONS_VERSION,
    ),
    ProtocolRule(
        text="A label changes only when a reviewer finds it wrong on its merits, "
        "never because the model disagreed. A change to any item's state, media, "
        "questions, gold, or split alters the dataset's content hash, which each "
        "run records, so runs on different label sets cannot be compared by "
        "accident; annotations (kind, tier, source, rationale) do not.",
        since=FOUNDATIONS_VERSION,
    ),
    ProtocolRule(
        text="Every `score` scale runs from least to most of the quantity its "
        "instruction names; index 0 is always the least. The expected score is "
        "read in those units. A scale is never reversed to make a label read "
        "naturally.",
        since=FOUNDATIONS_VERSION,
    ),
    ProtocolRule(
        text="For a `noul` question, P(true) is the probability of the condition "
        "the instruction names; the condition is phrased so that `true` is the "
        "pole that calls for caution.",
        since=FOUNDATIONS_VERSION,
    ),
)


def read_versions(path: Path = VERSIONS_PATH) -> list[str]:
    """Return every recorded dataset version, oldest first.

    Parameters
    ----------
    path : Path
        The lock file; one ``<content hash> <YYYY-MM-DD>`` line per version.

    Returns
    -------
    list[str]
        The content hashes in the order they were recorded (empty when absent).
    """
    if not path.exists():
        return []
    return [
        line.split()[0]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def record_version(
    content_sha256: str, *, path: Path = VERSIONS_PATH, recorded_on: str | None = None
) -> bool:
    """Append a dataset version to the lock unless it is already there.

    Parameters
    ----------
    content_sha256 : str
        The dataset's content hash.
    path : Path
        The lock file.
    recorded_on : str | None
        The date to record (today when ``None``).

    Returns
    -------
    bool
        ``True`` when a line was appended, ``False`` when already recorded.
    """
    if content_sha256 in read_versions(path):
        return False
    day = recorded_on or datetime.now(UTC).strftime("%Y-%m-%d")
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    write_atomic(path, f"{existing}{content_sha256} {day}\n")
    return True
