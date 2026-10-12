"""Convert a consented, redacted session into a candidate captured item."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..atomic import write_atomic
from .io import dump_item
from .records.capture_outcome import CaptureOutcome
from .records.item import Item
from .records.redaction_record import RedactionRecord
from .records.session_transcript import SessionTranscript
from .records.source import Source
from .records.source_kind import SourceKind
from .records.split import Split
from .register import load_example_secrets
from .secret_guard import no_live_secret

CANDIDATES_DIR = Path(__file__).parent / "candidates"


def convert(
    transcript: SessionTranscript,
    redaction: RedactionRecord,
) -> tuple[CaptureOutcome, Item | None]:
    """Convert a consented session to a candidate item, or refuse it.

    Parameters
    ----------
    transcript : SessionTranscript
        The session: turns plus the reviewed and acted choices.
    redaction : RedactionRecord
        The redaction provenance; its ``session_id`` MUST match the transcript's.

    Returns
    -------
    tuple[CaptureOutcome, Item | None]
        The outcome and, when converted, a schema-valid candidate whose source
        is ``captured`` (gold = the reviewed choice, ``acted`` = the in-session
        choice). ``None`` on any refusal; nothing is written by this function.
    """
    if redaction.session_id != transcript.session_id:
        return CaptureOutcome.refused_no_redaction, None
    state = "\n".join(f"{turn.role.value}: {turn.content}" for turn in transcript.turns)
    item = Item(
        id=f"captured_{transcript.session_id}",
        category=transcript.category,
        split=Split.dev,
        state=state,
        questions={transcript.question_id: transcript.question},
        gold_labels={transcript.question_id: transcript.reviewed_choice},
        rationale=f"captured from session {transcript.session_id}",
        source=Source(
            kind=SourceKind.captured,
            session_id=transcript.session_id,
            redaction_sha256=redaction.redaction_sha256,
        ),
        acted={"choice": transcript.acted_choice},
        acted_differs=transcript.acted_choice != transcript.reviewed_choice,
    )
    if no_live_secret([item], load_example_secrets()):
        return CaptureOutcome.refused_live_secret, None
    return CaptureOutcome.converted, item


def write_candidate(item: Item, out_dir: Path = CANDIDATES_DIR) -> Path:
    """Write the candidate to ``out_dir/<session-id>.jsonl`` atomically."""
    path = out_dir / f"{item.source.session_id}.jsonl"
    write_atomic(path, dump_item(item) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``ember eval capture import TRANSCRIPT REDACTION [--out DIR]``."""
    parser = argparse.ArgumentParser(prog="ember eval capture")
    sub = parser.add_subparsers(dest="capture_command", required=True)
    imp = sub.add_parser("import", help="convert a session into a candidate item")
    imp.add_argument("transcript", type=Path)
    imp.add_argument("redaction", type=Path)
    imp.add_argument("--out", type=Path, default=CANDIDATES_DIR)
    args = parser.parse_args(argv)
    try:
        transcript = SessionTranscript.model_validate_json(
            args.transcript.read_text(encoding="utf-8")
        )
        redaction = RedactionRecord.model_validate_json(
            args.redaction.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    outcome, item = convert(transcript, redaction)
    if outcome is not CaptureOutcome.converted or item is None:
        print(f"error: {outcome.value}", file=sys.stderr)
        return 1
    path = write_candidate(item, args.out)
    print(f"converted: {path}")
    return 0
