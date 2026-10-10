"""Compare a reproduction with the run it reproduces (contracts/eval-context.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..metrics import score_question
from .records.probe_row import ProbeRow
from .rows_file import read_rows
from .summarize import dataset_items, load_manifest, rows_name, summarize

PROBABILITY_TOLERANCE = 0.001
_COUNTS = ("total_tokens", "state_tokens", "media_tokens", "fixed_tokens")


def _numbers(value: Any, path: str = "") -> dict[str, float]:
    if isinstance(value, bool):
        return {}
    if isinstance(value, int | float):
        return {path: float(value)}
    if isinstance(value, dict):
        out: dict[str, float] = {}
        for key, inner in value.items():
            out.update(_numbers(inner, f"{path}.{key}" if path else str(key)))
        return out
    return {}


def _correctness(item: dict[str, Any], answers: dict[str, Any]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for qid, gold in item["gold_labels"].items():
        try:
            record = score_question(item["questions"][qid], gold, answers.get(qid))
            result[qid] = bool(record["correct"])
        except (KeyError, TypeError, ValueError):
            result[qid] = False
    return result


def _row_differences(
    original: ProbeRow, copy: ProbeRow, item: dict[str, Any]
) -> list[str]:
    label = f"{copy.model} {copy.item_id} {copy.length} {copy.depth}"
    out: list[str] = []
    for field in _COUNTS:
        before, after = getattr(original, field), getattr(copy, field)
        if before != after:
            out.append(f"{label}: {field.replace('_', ' ')} {before} -> {after}")
    if original.status != copy.status:
        out.append(f"{label}: status {original.status} -> {copy.status}")
    before_numbers, after_numbers = _numbers(original.answers), _numbers(copy.answers)
    for key in sorted(before_numbers.keys() | after_numbers.keys()):
        a, b = before_numbers.get(key), after_numbers.get(key)
        if a is None or b is None or abs(a - b) > PROBABILITY_TOLERANCE:
            out.append(f"{label}: probability {key} {a} -> {b}")
    after_correct = _correctness(item, copy.answers)
    for qid, ok in _correctness(item, original.answers).items():
        if after_correct.get(qid) != ok:
            out.append(f"{label}: {qid} correct {ok} -> {after_correct.get(qid)}")
    return out


def compare(original: Path, reproduction: Path, *, rows_only: bool) -> list[str]:
    """List every difference between two runs; empty means it reproduced.

    Rows are compared on counted tokens, status, every answer number (within
    ``PROBABILITY_TOLERANCE``), and per-question correctness. A full
    reproduction (``rows_only=False``) also needs the same rows on both sides
    and the same cap for every model; a subset compares shared rows only.
    """
    items = dataset_items(load_manifest(original), original)
    differences: list[str] = []
    for model in sorted(load_manifest(reproduction).models):
        before = {row.key: row for row in read_rows(original / rows_name(model))}
        after = {row.key: row for row in read_rows(reproduction / rows_name(model))}
        for key in sorted(before.keys() & after.keys()):
            differences += _row_differences(before[key], after[key], items[key[1]])
        if not rows_only:
            for key in sorted(before.keys() ^ after.keys()):
                side = "reproduction" if key in before else "original run"
                differences.append(
                    f"{' '.join(map(str, key))}: missing from the {side}"
                )
    if not rows_only:
        caps_before = {v.model: v.cap for v in summarize(original).verdicts}
        caps_after = {v.model: v.cap for v in summarize(reproduction).verdicts}
        for model in sorted(caps_before.keys() | caps_after.keys()):
            if caps_before.get(model) != caps_after.get(model):
                differences.append(
                    f"{model}: cap {caps_before.get(model)} -> {caps_after.get(model)}"
                )
    return differences
