"""Unit tests for the long-context probe (``evals/context``), with no model.

Covers the records, filler and padding, scoring and the cap rule, the summary, resume,
item selection, the sizing gate, reproduction, and the memory sampler.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from evals.context import (
    filler,
    items,
    padding,
    reproduce,
    rows_file,
    rule,
    run_context,
    scoring,
    summarize,
)
from evals.context.memory_sampler import MemorySampler
from evals.context.records.cell_result import CellResult
from evals.context.records.depth import Depth
from evals.context.records.failure_reason import FailureReason
from evals.context.records.length_verdict import LengthVerdict
from evals.context.records.model_verdict import ModelVerdict
from evals.context.records.probe_manifest import ProbeManifest, new_run_id
from evals.context.records.probe_model import ProbeModel
from evals.context.records.probe_row import ProbeRow
from evals.context.records.probe_summary import ProbeSummary
from evals.context.records.row_status import RowStatus
from evals.eval import provenance
from evals.metrics import bootstrap_ci, brier_binary, brier_multiclass
from pydantic import ValidationError

RUN_ID = "context_20261009T120000Z"
BUDGET = 32 * 2**30
ITEMS = [
    {
        "id": "a1",
        "category": "routing",
        "split": "dev",
        "state": "the database is down",
        "questions": {
            "team": {
                "type": "choice",
                "criteria": {"db": "Database issues", "web": "Frontend issues"},
            },
            "urgent": {"type": "noul"},
            "effort": {"type": "score", "criteria": ["low", "mid", "high"]},
        },
        "gold_labels": {"team": "db", "urgent": True, "effort": 2},
    },
    {
        "id": "b2",
        "category": "change_risk",
        "split": "test",
        "state": {"diff": "fix a typo"},
        "questions": {"urgent": {"type": "noul"}},
        "gold_labels": {"urgent": False},
    },
]
ITEM_BY_ID = {item["id"]: item for item in ITEMS}


def _answers(item_id: str, p_urgent: float | None = None, p_db: float = 0.8) -> dict:
    default = 0.9 if item_id == "a1" else 0.1
    urgent = {"type": "noul", "noul": default if p_urgent is None else p_urgent}
    if item_id == "b2":
        return {"urgent": urgent}
    return {
        "team": {
            "type": "choice",
            "choice": "db" if p_db >= 0.5 else "web",
            "confidence": max(p_db, 1 - p_db),
            "probabilities": {"db": p_db, "web": round(1 - p_db, 6)},
        },
        "urgent": urgent,
        "effort": {
            "type": "score",
            "score": 0.0,
            "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0},
        },
    }


def _model() -> ProbeModel:
    return ProbeModel(
        name="flash",
        repo="Cloudflare/clef-flash",
        revision="17f0b0ad64efb65d273590632833508766b2aae6",
        params="9B",
        memory_budget_bytes=BUDGET,
    )


def _manifest(**overrides: object) -> ProbeManifest:
    fields: dict[str, object] = {
        "run_id": RUN_ID,
        "created_at": "2026-10-09T12:00:00Z",
        "canonical": False,
        "git_hash": "c65e705",
        "git_dirty": False,
        "ember_version": "0.8.0",
        "host": {"platform": "test"},
        "device": "mps",
        "dtype": "float16",
        "models": {"flash": _model()},
        "dataset_path": "evals/clef-flash.jsonl",
        "dataset_sha256": "0" * 64,
        "item_ids": ["a1", "b2"],
        "excluded": {"m1": "media item"},
        "filler_path": "evals/context/filler.txt",
        "filler_sha256": filler.FILLER_SHA256,
        "filler_source": filler.FILLER_SOURCE,
        "filler_licence": filler.FILLER_LICENCE,
        "lengths": [2048, 4096],
        "exploratory_items": 2,
        "exploratory_item_ids": ["a1", "b2"],
    }
    fields.update(overrides)
    return ProbeManifest(**fields)


def _row(
    item_id: str = "a1",
    length: int = 2048,
    depth: Depth = Depth.MIDDLE,
    *,
    status: RowStatus = RowStatus.OK,
    answers: dict | None = None,
    total: int | None = None,
    latency: float = 100.0,
    exploratory: bool = False,
) -> ProbeRow:
    item = ITEM_BY_ID[item_id]
    total = length - 10 if total is None else total
    if answers is None:
        answers = _answers(item_id) if status is RowStatus.OK else {}
    return ProbeRow(
        run_id=RUN_ID,
        model="flash",
        item_id=item_id,
        split=item["split"],
        category=item["category"],
        length=length,
        depth=depth,
        total_tokens=total,
        state_tokens=total - 100,
        media_tokens=0,
        fixed_tokens=100,
        answers=answers,
        latency_ms=latency,
        rss_start_bytes=1000,
        driver_peak_bytes=2000,
        peak_bytes=3000,
        status=status,
        exploratory=exploratory,
        error=None if status is RowStatus.OK else "MPS backend out of memory",
    )


def _rows(lengths: tuple[int, ...] = (2048, 4096)) -> list[ProbeRow]:
    return [
        _row(item_id, length, depth)
        for length in lengths
        for depth in Depth
        for item_id in ("a1", "b2")
    ]


def _write_run(run_dir: Path, rows: list[ProbeRow], **manifest_fields: object) -> Path:
    run_dir.mkdir(parents=True)
    dataset = run_dir / "dataset.jsonl"
    dataset.write_text("".join(json.dumps(item) + "\n" for item in ITEMS))
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    manifest = _manifest(
        dataset_path=str(dataset), dataset_sha256=digest, **manifest_fields
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    lines = "".join(row.model_dump_json() + "\n" for row in rows)
    (run_dir / "rows-flash.jsonl").write_text(lines)
    return run_dir


def _cell(
    length: int,
    depth: Depth,
    accuracy: float,
    brier: float,
    *,
    exploratory: bool = False,
    delta_accuracy: float = 0.0,
    delta_brier: float = 0.0,
    n_errors: int = 0,
) -> CellResult:
    return CellResult(
        model="flash",
        length=length,
        depth=depth,
        exploratory=exploratory,
        n_items=10,
        accuracy=accuracy,
        brier=brier,
        ece=0.05,
        delta_accuracy=delta_accuracy,
        delta_accuracy_ci=(delta_accuracy, delta_accuracy),
        delta_brier=delta_brier,
        delta_brier_ci=(delta_brier, delta_brier),
        n_errors=n_errors,
    )


def _length_verdict(**overrides: object) -> LengthVerdict:
    fields: dict[str, object] = {
        "model": "flash",
        "length": 4096,
        "peak_bytes": 3000,
        "budget_bytes": BUDGET,
        "latency_ms_median": 120.0,
        "memory_ok": True,
        "quality_ok": False,
        "passes": False,
        "reason": FailureReason.ACCURACY,
        "failed_depth": Depth.END,
    }
    fields.update(overrides)
    return LengthVerdict(**fields)


def _model_verdict(**overrides: object) -> ModelVerdict:
    fields: dict[str, object] = {
        "model": "flash",
        "cap": 4096,
        "first_failure_length": 8192,
        "first_failure_reason": FailureReason.BRIER,
        "first_failure_depth": Depth.START,
    }
    fields.update(overrides)
    return ModelVerdict(**fields)


def _summary() -> ProbeSummary:
    return ProbeSummary(
        run_id=RUN_ID,
        canonical=False,
        rule={"tolerance_accuracy": 0.02, "tolerance_brier": 0.02},
        cells=[_cell(2048, Depth.START, 0.9, 0.1)],
        lengths=[_length_verdict()],
        verdicts=[_model_verdict()],
        inputs_sha256={"manifest.json": "0" * 64},
    )


# ###########################################################################
# T041: records
# ###########################################################################
def test_the_probe_enums_have_their_contract_values():
    assert [member.value for member in Depth] == ["start", "middle", "end"]
    assert [member.value for member in RowStatus] == ["ok", "oom", "error"]
    assert [member.value for member in FailureReason] == [
        "memory",
        "oom",
        "accuracy",
        "brier",
        "error",
    ]


def test_a_new_run_id_has_the_canonical_form():
    assert re.fullmatch(r"context_\d{8}T\d{6}Z", new_run_id())


def test_the_manifest_accepts_a_run_id_given_by_flag():
    assert _manifest(run_id="pilot-flash.1").run_id == "pilot-flash.1"


@pytest.mark.parametrize("run_id", ["", "../escape", "a/b", "two words"])
def test_the_manifest_rejects_a_run_id_that_is_not_a_safe_name(run_id):
    with pytest.raises(ValidationError):
        _manifest(run_id=run_id)


@pytest.mark.parametrize(
    "lengths", [[], [1024, 2048], [4096, 2048], [2048, 2048], [2048, 8192, 4096]]
)
def test_the_lengths_ascend_from_2048(lengths):
    with pytest.raises(ValidationError):
        _manifest(lengths=lengths)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("length_tolerance_tokens", 64),
        ("tolerance_accuracy", 0.05),
        ("tolerance_brier", 0.01),
        ("bootstrap_resamples", 1000),
        ("bootstrap_level", 0.9),
        ("seed", 1),
    ],
)
def test_the_rule_parameters_are_fixed(field, value):
    with pytest.raises(ValidationError):
        _manifest(**{field: value})


def test_the_exploratory_subset_is_drawn_from_the_items():
    with pytest.raises(ValidationError):
        _manifest(exploratory_item_ids=["a1", "zz"])
    with pytest.raises(ValidationError):
        _manifest(exploratory_item_ids=["a1"])


def test_the_exploratory_subset_has_48_items_when_there_are_enough():
    ids = [f"i{n:03d}" for n in range(60)]
    manifest = _manifest(
        item_ids=ids, exploratory_items=48, exploratory_item_ids=ids[:48]
    )
    assert len(manifest.exploratory_item_ids) == 48
    with pytest.raises(ValidationError):
        _manifest(item_ids=ids, exploratory_items=40, exploratory_item_ids=ids[:40])


def test_a_rows_token_parts_sum_to_its_total():
    row = _row()
    with pytest.raises(ValidationError):
        ProbeRow(**{**row.model_dump(), "state_tokens": row.state_tokens + 1})


@pytest.mark.parametrize(
    ("total", "valid"), [(2048, True), (2016, True), (2015, False)]
)
def test_an_ok_row_lands_within_32_tokens_below_its_length(total, valid):
    if valid:
        assert _row(total=total).total_tokens == total
    else:
        with pytest.raises(ValidationError):
            _row(total=total)


def test_an_ok_row_never_exceeds_its_length():
    with pytest.raises(ValidationError):
        _row(total=2049)


def test_only_an_ok_row_carries_answers():
    assert _row(status=RowStatus.OOM).answers == {}
    with pytest.raises(ValidationError):
        _row(status=RowStatus.OOM, answers=_answers("a1"))


def test_a_rows_peak_is_its_rss_start_plus_its_driver_peak():
    row = _row()
    assert row.peak_bytes == row.rss_start_bytes + row.driver_peak_bytes
    with pytest.raises(ValidationError):
        ProbeRow(**{**row.model_dump(), "peak_bytes": 2999})


def test_a_row_key_identifies_model_item_length_and_depth():
    assert _row("b2", 4096, Depth.END).key == ("flash", "b2", 4096, Depth.END)


def test_a_length_verdict_reason_is_a_failure_reason():
    with pytest.raises(ValidationError):
        _length_verdict(reason="slow")


def test_a_length_verdict_failed_depth_is_a_depth():
    with pytest.raises(ValidationError):
        _length_verdict(failed_depth="deep")


def test_a_failed_depth_is_set_only_for_a_quality_failure():
    with pytest.raises(ValidationError):
        _length_verdict(reason=FailureReason.MEMORY, memory_ok=False, quality_ok=None)
    with pytest.raises(ValidationError):
        _length_verdict(failed_depth=None)
    memory = _length_verdict(
        reason=FailureReason.MEMORY, failed_depth=None, memory_ok=False, quality_ok=None
    )
    assert memory.failed_depth is None


def test_a_passing_length_has_no_reason_and_a_failing_one_has_one():
    passing = _length_verdict(
        passes=True, quality_ok=True, reason=None, failed_depth=None
    )
    assert passing.reason is None
    with pytest.raises(ValidationError):
        _length_verdict(passes=True, quality_ok=True)
    with pytest.raises(ValidationError):
        _length_verdict(reason=None, failed_depth=None)


def test_a_model_verdicts_first_failure_fields_are_typed():
    assert _model_verdict().first_failure_reason is FailureReason.BRIER
    with pytest.raises(ValidationError):
        _model_verdict(first_failure_reason="slow")
    with pytest.raises(ValidationError):
        _model_verdict(first_failure_depth="deep")


def test_a_model_verdict_with_no_failure_has_no_failure_fields():
    clean = _model_verdict(
        cap=65536,
        first_failure_length=None,
        first_failure_reason=None,
        first_failure_depth=None,
    )
    assert clean.first_failure_length is None
    with pytest.raises(ValidationError):
        _model_verdict(first_failure_length=None)


@pytest.mark.parametrize(
    "factory",
    [_model, _manifest, _row, _summary, _length_verdict, _model_verdict],
)
def test_every_record_survives_a_json_round_trip(factory):
    record = factory()
    assert type(record).model_validate_json(record.model_dump_json()) == record


def test_a_cell_survives_a_json_round_trip():
    cell = _cell(4096, Depth.END, 0.9, 0.1, delta_accuracy=-0.01)
    assert CellResult.model_validate_json(cell.model_dump_json()) == cell


def test_git_dirty_reports_a_bool():
    assert isinstance(provenance.git_dirty(), bool)


# ###########################################################################
# T042: filler and padding
# ###########################################################################
class WordTokenizer:
    """One token per whitespace-separated word, over a fixed vocabulary."""

    def __init__(self, words: list[str]) -> None:
        self.words = words
        self.ids = {word: index for index, word in enumerate(words)}

    def __call__(self, text: str, add_special_tokens: bool = True) -> SimpleNamespace:
        return SimpleNamespace(input_ids=[self.ids[word] for word in text.split()])

    def decode(self, ids: list[int]) -> str:
        return " ".join(self.words[index] for index in ids)


WORDS = [f"w{n}" for n in range(5000)]
TOKENIZER = WordTokenizer(WORDS)
FILLER_IDS = list(range(len(WORDS)))
EVIDENCE = "the payment service returns HTTP 500 for every request"
OVERHEAD = 7


def _count(state: str) -> int:
    return len(state.split()) + OVERHEAD


def _count_double_filler(state: str) -> int:
    return sum(2 if word.startswith("w") else 1 for word in state.split()) + OVERHEAD


def test_load_filler_rejects_a_changed_file(tmp_path):
    path = tmp_path / "filler.txt"
    path.write_text("call me ishmael", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        filler.load_filler(path, "0" * 64)


def test_load_filler_returns_the_verified_text(tmp_path):
    path = tmp_path / "filler.txt"
    path.write_text("call me ishmael", encoding="utf-8")
    digest = hashlib.sha256(b"call me ishmael").hexdigest()
    assert filler.load_filler(path, digest) == "call me ishmael"


def test_the_vendored_filler_matches_its_pinned_digest():
    digest = hashlib.sha256(filler.FILLER_PATH.read_bytes()).hexdigest()
    assert digest == filler.FILLER_SHA256


def test_filler_ids_tokenize_without_special_tokens():
    calls: list[bool] = []

    class Recording(WordTokenizer):
        def __call__(self, text: str, add_special_tokens: bool = True):
            calls.append(add_special_tokens)
            return super().__call__(text, add_special_tokens)

    assert filler.filler_ids(Recording(WORDS), "w3 w1 w2") == [3, 1, 2]
    assert calls == [False]


def test_offset_for_is_deterministic_and_in_range():
    for item_id in ("a1", "b2", "routing_017", "intent_001"):
        offset = filler.offset_for(item_id, 300, 1000)
        assert offset == filler.offset_for(item_id, 300, 1000)
        assert 0 <= offset <= 1000 - 300
    assert filler.offset_for("a1", 1000, 1000) == 0


def test_offset_for_refuses_a_filler_that_is_too_short():
    with pytest.raises(ValueError, match="filler"):
        filler.offset_for("a1", 1001, 1000)


@pytest.mark.parametrize("target", [256, 1024, 2048])
@pytest.mark.parametrize("depth", list(Depth))
def test_build_state_lands_within_the_tolerance(depth, target):
    state = padding.build_state(
        EVIDENCE, FILLER_IDS, TOKENIZER, depth, target, _count, offset=10
    )
    assert target - 32 <= _count(state) <= target


@pytest.mark.parametrize("depth", list(Depth))
def test_build_state_converges_when_filler_tokens_cost_more(depth):
    state = padding.build_state(
        EVIDENCE, FILLER_IDS, TOKENIZER, depth, 1024, _count_double_filler, offset=0
    )
    assert 1024 - 32 <= _count_double_filler(state) <= 1024


@pytest.mark.parametrize("depth", list(Depth))
def test_the_evidence_is_embedded_verbatim_between_separators(depth):
    state = padding.build_state(
        EVIDENCE, FILLER_IDS, TOKENIZER, depth, 512, _count, offset=0
    )
    assert state.count("\n\n" + EVIDENCE + "\n\n") == 1


def test_start_puts_the_evidence_before_all_filler():
    state = padding.build_state(
        EVIDENCE, FILLER_IDS, TOKENIZER, Depth.START, 512, _count, offset=0
    )
    assert state.startswith("\n\n" + EVIDENCE + "\n\n")


def test_end_puts_the_evidence_after_all_filler():
    state = padding.build_state(
        EVIDENCE, FILLER_IDS, TOKENIZER, Depth.END, 512, _count, offset=0
    )
    assert state.endswith("\n\n" + EVIDENCE + "\n\n")


def test_middle_puts_the_evidence_in_the_center():
    state = padding.build_state(
        EVIDENCE, FILLER_IDS, TOKENIZER, Depth.MIDDLE, 512, _count, offset=0
    )
    before, after = state.split("\n\n" + EVIDENCE + "\n\n")
    assert before
    assert abs(len(before.split()) - len(after.split())) <= 1


def test_build_state_refuses_evidence_that_leaves_too_little_room():
    evidence = " ".join(["x"] * 300)
    with pytest.raises(ValueError, match="evidence"):
        padding.build_state(
            evidence, FILLER_IDS, TOKENIZER, Depth.MIDDLE, 300, _count, offset=0
        )


# ###########################################################################
# T043: scoring and the cap rule
# ###########################################################################
def test_item_scores_use_only_the_noul_and_choice_questions():
    score = scoring.item_scores(ITEMS[0], _answers("a1"))
    expected = statistics.mean(
        [
            brier_binary([0.9], [True]),
            brier_multiclass([{"db": 0.8, "web": 0.2}], ["db"]),
        ]
    )
    assert score.accuracy == 1.0
    assert score.brier == pytest.approx(expected)
    assert len(score.correct) == len(score.confidences) == 2


def test_item_scores_count_a_wrong_answer():
    assert scoring.item_scores(ITEMS[0], _answers("a1", p_urgent=0.2)).accuracy == 0.5


def test_paired_deltas_pair_items_by_id():
    base = {"a": 1.0, "b": 0.5, "c": 1.0}
    other = {"b": 1.0, "a": 0.0, "d": 1.0}
    assert scoring.paired_deltas(base, other) == [-1.0, 0.5]


def test_delta_ci_is_deterministic_with_seed_0():
    deltas = [0.0, -0.5, 0.5, -1.0, 0.0, 0.25]
    first = scoring.delta_ci(deltas, resamples=10000, level=0.95, seed=0)
    assert first == scoring.delta_ci(deltas, resamples=10000, level=0.95, seed=0)
    assert first == bootstrap_ci(deltas, resamples=10000, level=0.95, seed=0)


def _cells(scores: dict[int, tuple[float, float]]) -> list[CellResult]:
    return [
        _cell(length, depth, accuracy, brier)
        for length, (accuracy, brier) in scores.items()
        for depth in Depth
    ]


def _memory(
    lengths: list[int], *, over: tuple[int, ...] = (), oom: tuple[int, ...] = ()
) -> dict[int, rule.LengthMemory]:
    return {
        length: rule.LengthMemory(
            peak_bytes=BUDGET + 1 if length in over else BUDGET // 2,
            oom=length in oom,
            latency_ms_median=100.0,
        )
        for length in lengths
    }


def _evaluate(cells, memory):
    return rule.evaluate(
        cells,
        memory,
        model="flash",
        tolerance_accuracy=0.02,
        tolerance_brier=0.02,
        budget_bytes=BUDGET,
    )


def test_a_length_at_the_tolerance_at_every_depth_passes():
    cells = _cells({2048: (0.90, 0.10), 4096: (0.88, 0.12)})
    verdicts, verdict = _evaluate(cells, _memory([2048, 4096]))
    assert [v.passes for v in verdicts] == [True, True]
    assert (verdict.cap, verdict.first_failure_length) == (4096, None)


def test_one_failing_depth_fails_the_length():
    cells = [
        *_cells({2048: (0.90, 0.10)}),
        _cell(4096, Depth.START, 0.90, 0.10),
        _cell(4096, Depth.MIDDLE, 0.87, 0.10),
        _cell(4096, Depth.END, 0.90, 0.10),
    ]
    verdicts, verdict = _evaluate(cells, _memory([2048, 4096]))
    failed = verdicts[1]
    assert (failed.passes, failed.reason, failed.failed_depth) == (
        False,
        FailureReason.ACCURACY,
        Depth.MIDDLE,
    )
    assert verdict.cap == 2048
    assert verdict.first_failure_reason is FailureReason.ACCURACY
    assert verdict.first_failure_depth is Depth.MIDDLE


def test_a_brier_rise_beyond_the_tolerance_fails_the_length():
    cells = _cells({2048: (0.90, 0.10), 4096: (0.90, 0.13)})
    verdicts, _ = _evaluate(cells, _memory([2048, 4096]))
    assert (verdicts[1].reason, verdicts[1].failed_depth) == (
        FailureReason.BRIER,
        Depth.START,
    )


def test_a_pass_after_a_failure_does_not_raise_the_cap():
    cells = _cells({2048: (0.9, 0.1), 4096: (0.8, 0.1), 8192: (0.9, 0.1)})
    verdicts, verdict = _evaluate(cells, _memory([2048, 4096, 8192]))
    assert [v.passes for v in verdicts] == [True, False, True]
    assert (verdict.cap, verdict.first_failure_length) == (2048, 4096)


def test_a_memory_failure_fails_that_length_and_every_longer_one():
    cells = _cells({2048: (0.9, 0.1), 4096: (0.9, 0.1), 8192: (0.9, 0.1)})
    verdicts, verdict = _evaluate(cells, _memory([2048, 4096, 8192], over=(4096,)))
    assert [(v.passes, v.reason) for v in verdicts] == [
        (True, None),
        (False, FailureReason.MEMORY),
        (False, FailureReason.MEMORY),
    ]
    assert verdicts[1].quality_ok is None
    assert verdict.cap == 2048
    assert verdict.first_failure_reason is FailureReason.MEMORY
    assert verdict.first_failure_depth is None


def test_an_oom_fails_that_length_and_every_longer_one():
    cells = _cells({2048: (0.9, 0.1), 4096: (0.9, 0.1)})
    verdicts, verdict = _evaluate(cells, _memory([2048, 4096, 8192], oom=(4096,)))
    assert [v.reason for v in verdicts] == [
        None,
        FailureReason.OOM,
        FailureReason.OOM,
    ]
    assert verdict.first_failure_reason is FailureReason.OOM


def test_there_is_no_cap_when_no_length_passes():
    cells = _cells({2048: (0.9, 0.1)})
    _, verdict = _evaluate(cells, _memory([2048], over=(2048,)))
    assert (verdict.cap, verdict.first_failure_length) == (None, 2048)


def test_exploratory_cells_are_judged_on_their_paired_deltas():
    cells = _cells({2048: (0.9, 0.1), 4096: (0.8, 0.1)}) + [
        _cell(8192, depth, 0.5, 0.4, exploratory=True, delta_accuracy=-0.01)
        for depth in Depth
    ]
    verdicts, verdict = _evaluate(cells, _memory([2048, 4096, 8192]))
    assert verdicts[2].passes is True
    assert verdict.cap == 2048


def test_a_missing_cell_fails_the_length():
    cells = [*_cells({2048: (0.9, 0.1)}), _cell(4096, Depth.START, 0.9, 0.1)]
    verdicts, _ = _evaluate(cells, _memory([2048, 4096]))
    assert (verdicts[1].passes, verdicts[1].reason, verdicts[1].failed_depth) == (
        False,
        FailureReason.ERROR,
        Depth.MIDDLE,
    )


def test_a_cell_with_an_errored_inference_fails_the_length():
    cells = [
        *_cells({2048: (0.9, 0.1)}),
        _cell(4096, Depth.START, 0.9, 0.1),
        _cell(4096, Depth.MIDDLE, 0.9, 0.1, n_errors=1),
        _cell(4096, Depth.END, 0.9, 0.1),
    ]
    verdicts, verdict = _evaluate(cells, _memory([2048, 4096]))
    assert (verdicts[1].reason, verdicts[1].failed_depth) == (
        FailureReason.ERROR,
        Depth.MIDDLE,
    )
    assert verdict.cap == 2048


# ###########################################################################
# T044: summary, resume, items, the sizing gate, reproduction, no MPS
# ###########################################################################
def test_summarize_is_byte_for_byte_deterministic(tmp_path):
    run_dir = _write_run(tmp_path / "run", _rows())
    first = summarize.write_summary(run_dir).read_bytes()
    second = summarize.write_summary(run_dir).read_bytes()
    assert first == second
    body = json.loads(first)
    assert list(body) == sorted(body)
    assert not re.findall(rb"\d\.\d{7,}", first)


def test_the_summary_applies_the_rule(tmp_path):
    summary = summarize.summarize(_write_run(tmp_path / "run", _rows()))
    assert [(v.model, v.cap) for v in summary.verdicts] == [("flash", 4096)]
    assert {(c.length, c.depth) for c in summary.cells} == {
        (length, depth) for length in (2048, 4096) for depth in Depth
    }
    baseline = next(c for c in summary.cells if c.length == 2048)
    assert (baseline.delta_accuracy, baseline.delta_accuracy_ci) == (0.0, (0.0, 0.0))


def test_the_summary_records_the_median_latency_of_ok_rows(tmp_path):
    rows = [
        row.model_copy(update={"latency_ms": 100.0 * (index + 1)})
        for index, row in enumerate(_rows(lengths=(2048,)))
    ]
    rows[-1] = _row("b2", 2048, Depth.END, status=RowStatus.ERROR, latency=9999.0)
    summary = summarize.summarize(_write_run(tmp_path / "run", rows))
    verdict = next(v for v in summary.lengths if v.length == 2048)
    assert verdict.latency_ms_median == statistics.median(
        [100.0, 200.0, 300.0, 400.0, 500.0]
    )


def test_an_errored_inference_is_counted_and_fails_its_length(tmp_path):
    rows = _rows()
    rows[-1] = _row("b2", 4096, Depth.END, status=RowStatus.ERROR)
    summary = summarize.summarize(_write_run(tmp_path / "run", rows))
    cell = next(c for c in summary.cells if (c.length, c.depth) == (4096, Depth.END))
    assert (cell.n_items, cell.n_errors) == (1, 1)
    verdict = next(v for v in summary.lengths if v.length == 4096)
    assert (verdict.reason, verdict.failed_depth) == (FailureReason.ERROR, Depth.END)
    assert summary.verdicts[0].cap == 2048


def test_the_summary_digests_its_inputs(tmp_path):
    run_dir = _write_run(tmp_path / "run", _rows())
    summary = summarize.summarize(run_dir)
    assert summary.inputs_sha256 == {
        name: hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
        for name in ("manifest.json", "rows-flash.jsonl")
    }


def test_the_summary_refuses_a_changed_dataset(tmp_path):
    run_dir = _write_run(tmp_path / "run", _rows())
    with (run_dir / "dataset.jsonl").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="dataset"):
        summarize.summarize(run_dir)


def test_the_summary_refuses_a_duplicate_row(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        summarize.summarize(_write_run(tmp_path / "run", [*_rows(), _row()]))


def test_a_torn_last_line_is_dropped_and_repaired(tmp_path):
    path = tmp_path / "rows-flash.jsonl"
    rows = [_row("a1"), _row("b2")]
    text = "".join(row.model_dump_json() + "\n" for row in rows)
    path.write_text(text + rows[0].model_dump_json()[:40])
    assert rows_file.read_rows(path) == rows
    rows_file.repair(path)
    assert path.read_text() == text
    rows_file.append_row(path, _row("a1", depth=Depth.END))
    assert len(rows_file.read_rows(path)) == 3


def test_a_missing_rows_file_has_no_rows(tmp_path):
    assert rows_file.read_rows(tmp_path / "rows-full.jsonl") == []


def test_finished_keys_are_skipped():
    done = [_row("a1", 2048, Depth.START)]
    planned = [
        ("flash", "a1", 2048, Depth.START),
        ("flash", "a1", 2048, Depth.MIDDLE),
    ]
    assert rows_file.pending(planned, done) == [("flash", "a1", 2048, Depth.MIDDLE)]


DATASET = [
    {"id": "t1", "category": "routing", "state": "a"},
    {"id": "m1", "category": "vision_noul", "state": "b", "images": ["data:x"]},
    {"id": "v1", "category": "vision_video", "state": "c", "videos": [["data:x"]]},
    {"id": "big", "category": "routing", "state": "d"},
    {"id": "t2", "category": "change_risk", "state": "e"},
]


def test_item_selection_keeps_text_only_items_and_records_every_exclusion():
    kept, excluded = items.select_items(
        DATASET, lambda item: 5000 if item["id"] == "big" else 300
    )
    assert [item["id"] for item in kept] == ["t1", "t2"]
    assert excluded["m1"] == excluded["v1"] == "media item"
    assert "5000" in excluded["big"]
    assert "1984" in excluded["big"]
    assert set(excluded) == {"m1", "v1", "big"}


def test_the_exploratory_subset_is_seeded_and_stratified():
    pool = [{"id": f"r{n:02d}", "category": "routing"} for n in range(30)]
    pool += [{"id": f"c{n:02d}", "category": "change_risk"} for n in range(10)]
    order = [item["id"] for item in pool]
    first = items.exploratory_subset(pool, 8, seed=0)
    assert first == items.exploratory_subset(pool, 8, seed=0)
    assert len(set(first)) == 8
    assert sum(item_id.startswith("r") for item_id in first) == 6
    assert sum(item_id.startswith("c") for item_id in first) == 2
    assert first == sorted(first, key=order.index)


def test_the_exploratory_subset_takes_every_item_when_there_are_few():
    pool = [{"id": f"r{n}", "category": "routing"} for n in range(3)]
    assert items.exploratory_subset(pool, 48, seed=0) == ["r0", "r1", "r2"]


def test_the_projected_half_width_is_1_96_sd_over_root_n():
    deltas = [0.0, 0.5, -0.5, 0.25, -0.25, 0.0]
    expected = 1.96 * statistics.stdev(deltas) / math.sqrt(len(deltas))
    assert scoring.projected_half_width(deltas) == pytest.approx(expected)


def test_the_sizing_gate_passes_only_within_two_points():
    tight = [0.01, -0.01] * 50
    loose = [0.5, -0.5] * 10
    assert scoring.projected_half_width(tight) <= 0.02
    assert scoring.projected_half_width(loose) > 0.02
    assert math.isinf(scoring.projected_half_width([0.1]))


def _reproduced(tmp_path, rows: list[ProbeRow]) -> tuple[Path, Path]:
    return _write_run(tmp_path / "a", _rows()), _write_run(tmp_path / "b", rows)


def _with_answer(rows: list[ProbeRow], index: int, **changes: float) -> list[ProbeRow]:
    rows = list(rows)
    row = rows[index]
    rows[index] = row.model_copy(update={"answers": _answers(row.item_id, **changes)})
    return rows


def test_an_identical_run_reproduces(tmp_path):
    original, copy = _reproduced(tmp_path, _rows())
    assert reproduce.compare(original, copy, rows_only=False) == []


def test_a_token_count_difference_is_flagged(tmp_path):
    rows = _rows()
    first = rows[0]
    rows[0] = first.model_copy(
        update={
            "total_tokens": first.total_tokens - 1,
            "state_tokens": first.state_tokens - 1,
        }
    )
    differences = reproduce.compare(*_reproduced(tmp_path, rows), rows_only=True)
    assert any("tokens" in line for line in differences)


def test_a_probability_change_over_0_001_is_flagged(tmp_path):
    rows = _with_answer(_rows(), 0, p_urgent=0.902)
    differences = reproduce.compare(*_reproduced(tmp_path, rows), rows_only=True)
    assert any("probability" in line for line in differences)


def test_a_probability_change_within_0_001_is_not_flagged(tmp_path):
    rows = _with_answer(_rows(), 0, p_urgent=0.9005)
    assert reproduce.compare(*_reproduced(tmp_path, rows), rows_only=True) == []


def test_a_change_in_correctness_is_flagged(tmp_path):
    rows = _with_answer(_rows(), 0, p_urgent=0.4)
    differences = reproduce.compare(*_reproduced(tmp_path, rows), rows_only=True)
    assert any("correct" in line for line in differences)


def test_a_cap_change_is_compared_only_in_a_full_reproduction(tmp_path):
    rows = _rows()
    for index, row in enumerate(rows):
        if row.length == 4096 and row.item_id == "a1":
            rows = _with_answer(rows, index, p_urgent=0.4)
    original, copy = _reproduced(tmp_path, rows)
    full = reproduce.compare(original, copy, rows_only=False)
    subset = reproduce.compare(original, copy, rows_only=True)
    assert any("cap" in line for line in full)
    assert subset
    assert not any("cap" in line for line in subset)


def test_the_probe_refuses_to_run_without_mps(monkeypatch, capsys):
    import torch

    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    assert run_context.main(["--smoke"]) == 1
    assert "MPS" in capsys.readouterr().err


# ###########################################################################
# T045: the memory sampler
# ###########################################################################
def test_the_sampler_keeps_the_highest_driver_reading():
    level = {"bytes": 10}
    sampler = MemorySampler(
        read_driver=lambda: level["bytes"], read_rss=lambda: 1000, interval=0.001
    )
    with sampler:
        level["bytes"] = 500
        time.sleep(0.05)
        level["bytes"] = 20
        time.sleep(0.02)
    assert sampler.driver_peak_bytes == 500


def test_the_peak_is_the_rss_start_plus_the_driver_peak():
    sampler = MemorySampler(
        read_driver=lambda: 300, read_rss=lambda: 1000, interval=0.001
    )
    with sampler:
        time.sleep(0.01)
    assert sampler.rss_start_bytes == 1000
    assert sampler.peak_bytes == 1300


def test_the_sampling_thread_stops_on_exit():
    sampler = MemorySampler(read_driver=lambda: 1, read_rss=lambda: 1, interval=0.001)
    with sampler:
        assert sampler.running
    assert not sampler.running


def test_an_error_inside_the_sampled_block_propagates():
    sampler = MemorySampler(read_driver=lambda: 1, read_rss=lambda: 1, interval=0.001)
    with pytest.raises(RuntimeError, match="boom"), sampler:
        raise RuntimeError("boom")
    assert not sampler.running


# ###########################################################################
# run_context: the sizing gate and reproductions (PR #94 review)
# ###########################################################################
def test_a_failed_sizing_gate_clears_canonical():
    manifest = _manifest(canonical=True)
    failed = run_context._gate_result(manifest, 0.05)
    passed = run_context._gate_result(manifest, 0.01)
    assert (failed.sizing_passed, failed.canonical) == (False, False)
    assert (passed.sizing_passed, passed.canonical) == (True, True)
    assert failed.pilot_projected_half_width == 0.05
    assert (
        run_context._gate_result(manifest, math.inf).pilot_projected_half_width is None
    )


def _probe_dirs(monkeypatch, tmp_path):
    import torch

    results, runs = tmp_path / "results", tmp_path / "runs"
    monkeypatch.setattr(run_context, "RESULTS_DIR", results)
    monkeypatch.setattr(run_context, "RUNS_DIR", runs)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    monkeypatch.setattr(run_context.process, "is_up", lambda *args: False)
    return results, runs


def test_resuming_a_run_whose_gate_failed_exits_2(monkeypatch, tmp_path, capsys):
    results, _ = _probe_dirs(monkeypatch, tmp_path)
    (results / RUN_ID).mkdir(parents=True)
    manifest = _manifest(sizing_passed=False, pilot_projected_half_width=0.05)
    (results / RUN_ID / "manifest.json").write_text(manifest.model_dump_json())
    assert run_context.main(["--resume", RUN_ID]) == 2
    assert "sizing gate" in capsys.readouterr().err


def test_a_reproduction_carries_the_snapshot_dataset(monkeypatch, tmp_path):
    import argparse

    _, runs = _probe_dirs(monkeypatch, tmp_path)
    snapshot = runs / RUN_ID
    snapshot.mkdir(parents=True)
    (snapshot / "dataset.jsonl").write_text(
        "".join(json.dumps(i) + "\n" for i in ITEMS)
    )
    (snapshot / "manifest.json").write_text(_manifest().model_dump_json())
    args = argparse.Namespace(resume=None, reproduce=RUN_ID, items=None)
    run_dir, manifest, original = run_context._prepare(args)
    assert (original, manifest.reproduces) == (snapshot, RUN_ID)
    copied = (run_dir / "dataset.jsonl").read_bytes()
    assert copied == (snapshot / "dataset.jsonl").read_bytes()


# ###########################################################################
# worker: the run's pinned weights and filler (PR #94 review)
# ###########################################################################
def test_check_pins_accepts_the_pinned_revision():
    from evals.context import worker

    worker.check_pins(_manifest(), "flash")


def test_check_pins_refuses_a_registry_revision_the_run_did_not_pin(monkeypatch):
    import dataclasses

    from ember import models
    from evals.context import worker

    spec = dataclasses.replace(models.REGISTRY["flash"], revision="0" * 40)
    monkeypatch.setitem(models.REGISTRY, "flash", spec)
    with pytest.raises(RuntimeError, match="pinned"):
        worker.check_pins(_manifest(), "flash")


def test_pinned_filler_reads_and_verifies_the_manifest_copy(tmp_path):
    from evals.context import worker

    path = tmp_path / "filler.txt"
    path.write_text("call me ishmael", encoding="utf-8")
    digest = hashlib.sha256(b"call me ishmael").hexdigest()
    manifest = _manifest(filler_path=str(path), filler_sha256=digest)
    assert worker.pinned_filler(manifest) == "call me ishmael"
    with pytest.raises(ValueError, match="SHA-256"):
        worker.pinned_filler(_manifest(filler_path=str(path)))


# ###########################################################################
# run_context: snapshots, the pilot's pairs, and resumed reproductions
# ###########################################################################
def test_a_snapshot_refuses_a_run_that_is_not_finished_and_canonical(
    monkeypatch, tmp_path, capsys
):
    results, runs = _probe_dirs(monkeypatch, tmp_path)
    _write_run(results / RUN_ID, _rows())
    assert run_context.main(["--snapshot", RUN_ID]) == 1
    assert "canonical" in capsys.readouterr().err
    assert not (runs / RUN_ID).exists()


def test_a_snapshot_copies_a_finished_canonical_run(monkeypatch, tmp_path):
    results, runs = _probe_dirs(monkeypatch, tmp_path)
    run = _write_run(
        results / RUN_ID, _rows(), canonical=True, sizing_passed=True, completed=True
    )
    summarize.write_summary(run)
    assert run_context.main(["--snapshot", RUN_ID]) == 0
    assert sorted(path.name for path in (runs / RUN_ID).iterdir()) == [
        "dataset.jsonl",
        "manifest.json",
        "rows-flash.jsonl",
        "summary.json",
    ]


def test_the_sizing_gate_fails_when_a_pilot_pair_is_missing():
    manifest = _manifest(lengths=[2048, 16384])
    rows = [
        _row(item_id, length, Depth.MIDDLE)
        for item_id in ("a1", "b2")
        for length in (2048, 16384)
    ]
    assert math.isfinite(run_context._pilot_width(manifest, rows, ITEM_BY_ID))
    assert math.isinf(run_context._pilot_width(manifest, rows[:-1], ITEM_BY_ID))


def test_resuming_a_reproduction_keeps_its_comparison_target(monkeypatch, tmp_path):
    import argparse

    results, runs = _probe_dirs(monkeypatch, tmp_path)
    original = _write_run(runs / RUN_ID, _rows())
    copy_id = "context_20261010T000000Z"
    (results / copy_id).mkdir(parents=True)
    copy = _manifest(run_id=copy_id, reproduces=RUN_ID)
    (results / copy_id / "manifest.json").write_text(copy.model_dump_json())
    args = argparse.Namespace(resume=copy_id, reproduce=None, items=None)
    _, manifest, original_dir = run_context._prepare(args)
    assert (manifest.reproduces, original_dir) == (RUN_ID, original)


def test_a_snapshot_refuses_a_rescored_run_that_never_finished(monkeypatch, tmp_path):
    results, runs = _probe_dirs(monkeypatch, tmp_path)
    run = _write_run(results / RUN_ID, _rows(), canonical=True, sizing_passed=True)
    summarize.write_summary(run)
    assert run_context.main(["--snapshot", RUN_ID]) == 1
    assert not (runs / RUN_ID).exists()


@pytest.mark.parametrize(
    ("chosen", "canonical"), [(None, True), ("flash,full", True), ("flash", False)]
)
def test_a_run_over_a_subset_of_the_models_is_not_canonical(chosen, canonical):
    import argparse

    args = argparse.Namespace(smoke=False, items=None, lengths=None, models=chosen)
    names = chosen.split(",") if chosen else ["flash", "full"]
    assert run_context._canonical(args, names) is canonical


def test_a_resumed_worker_takes_its_first_failure_only_from_finished_lengths():
    from evals.context import worker

    summary = _summary().model_copy(
        update={
            "lengths": [
                _length_verdict(
                    length=2048,
                    passes=True,
                    quality_ok=True,
                    reason=None,
                    failed_depth=None,
                ),
                _length_verdict(length=4096),
                _length_verdict(length=8192),
            ]
        }
    )
    assert worker.first_failure_at(summary, "flash", 2048) is None
    assert worker.first_failure_at(summary, "flash", 4096) == 4096
    assert worker.first_failure_at(summary, "flash", 8192) == 4096
