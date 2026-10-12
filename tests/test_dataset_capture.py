"""Unit tests for the session-capture converter (specs/006, US6)."""

from __future__ import annotations

import json
from pathlib import Path

from evals.dataset import capture
from evals.dataset.records.capture_outcome import CaptureOutcome
from evals.dataset.records.redaction_record import RedactionRecord
from evals.dataset.records.session_transcript import SessionTranscript

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _transcript(**overrides: object) -> SessionTranscript:
    fields: dict[str, object] = {
        "session_id": "s-1",
        "category": "failure_triage",
        "question_id": "failure_kind",
        "question": {
            "type": "choice",
            "criteria": {"flaky": "a flaky test", "real": "a real failure"},
        },
        "turns": [
            {"role": "user", "content": "CI failed on the fixtures test"},
            {"role": "agent", "content": "re-running the job"},
        ],
        "reviewed_choice": "flaky",
        "acted_choice": "real",
    }
    fields.update(overrides)
    return SessionTranscript.model_validate(fields)


def _redaction(**overrides: object) -> RedactionRecord:
    fields: dict[str, object] = {
        "session_id": "s-1",
        "redaction_sha256": "a" * 64,
        "method": "scrubbed tokens and hosts",
        "redacted_on": "2026-10-11",
    }
    fields.update(overrides)
    return RedactionRecord.model_validate(fields)


def test_a_clean_session_converts_to_a_captured_item() -> None:
    outcome, item = capture.convert(_transcript(), _redaction())
    assert outcome is CaptureOutcome.converted
    assert item is not None
    assert item.source.kind.value == "captured"
    assert item.source.session_id == "s-1"
    assert item.source.redaction_sha256 == "a" * 64
    assert item.gold_labels["failure_kind"] == "flaky"
    assert item.acted == {"choice": "real"}
    assert item.acted_differs is True


def test_matching_choices_do_not_tag_a_disagreement() -> None:
    outcome, item = capture.convert(_transcript(acted_choice="flaky"), _redaction())
    assert outcome is CaptureOutcome.converted
    assert item is not None
    assert item.acted_differs is False


def test_a_mismatched_redaction_record_is_refused() -> None:
    outcome, item = capture.convert(_transcript(), _redaction(session_id="other"))
    assert outcome is CaptureOutcome.refused_no_redaction
    assert item is None


def test_a_surviving_live_secret_is_refused() -> None:
    transcript = _transcript(
        turns=[{"role": "user", "content": "export AKIA1234567890ABCDEF"}]
    )
    outcome, item = capture.convert(transcript, _redaction())
    assert outcome is CaptureOutcome.refused_live_secret
    assert item is None


def test_main_converts_the_fixture_and_refuses_cleanly(tmp_path: Path) -> None:
    code = capture.main(
        [
            "import",
            str(FIXTURES / "session.json"),
            str(FIXTURES / "session.redaction.json"),
            "--out",
            str(tmp_path),
        ]
    )
    assert code == 0
    written = list(tmp_path.glob("*.jsonl"))
    assert written, "the candidate must be written"
    item = json.loads(written[0].read_text(encoding="utf-8").strip())
    assert item["source"]["kind"] == "captured"
    assert item["source"]["session_id"] == "fixture-session-1"

    again = capture.main(
        [
            "import",
            str(FIXTURES / "session.json"),
            str(FIXTURES / "missing.redaction.json"),
            "--out",
            str(tmp_path / "refused"),
        ]
    )
    assert again == 2
    assert not list((tmp_path / "refused").glob("*.jsonl"))
