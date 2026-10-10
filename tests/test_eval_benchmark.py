"""Benchmark integrity and scoring: the dataset is well formed and the metrics
match hand-computed values. Nothing here loads the model.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest
from evals import metrics

DATASET = Path(__file__).resolve().parents[1] / "evals" / "clef-flash.jsonl"
ITEMS = [
    json.loads(line)
    for line in DATASET.read_text(encoding="utf-8").splitlines()
    if line.strip()
]


def _labels(spec: dict) -> set:
    if spec["type"] == "choice":
        return set(spec["criteria"])
    if spec["type"] == "noul":
        return {True, False}
    return set(range(len(spec["criteria"])))


def _answers(item: dict, *, right: bool) -> dict:
    """Confident answers that hit (or miss) every gold label of ``item``."""
    answers = {}
    for qid, gold in item["gold_labels"].items():
        spec = item["questions"][qid]
        if spec["type"] == "choice":
            options = list(spec["criteria"])
            pick = gold if right else next(o for o in options if o != gold)
            probabilities = {
                o: (0.9 if o == pick else 0.1 / (len(options) - 1)) for o in options
            }
            answers[qid] = {
                "type": "choice",
                "choice": pick,
                "confidence": 0.9,
                "probabilities": probabilities,
            }
        elif spec["type"] == "noul":
            answers[qid] = {"type": "noul", "noul": 0.9 if gold == right else 0.1}
        else:
            level = gold if right else (gold + 2) % len(spec["criteria"])
            probabilities = {
                str(k): float(k == level) for k in range(len(spec["criteria"]))
            }
            answers[qid] = {
                "type": "score",
                "score": float(level),
                "probabilities": probabilities,
            }
    return answers


# ###########################################################################
# Dataset
# ###########################################################################


def test_dataset_has_at_least_100_unique_items() -> None:
    assert len(ITEMS) >= 100
    assert len({item["id"] for item in ITEMS}) == len(ITEMS)


def test_every_question_has_a_valid_gold_label_and_rationale() -> None:
    for item in ITEMS:
        assert item["split"] in {"dev", "test"}, item["id"]
        assert item["rationale"].strip(), item["id"]
        assert set(item["gold_labels"]) == set(item["questions"]), item["id"]
        for qid, gold in item["gold_labels"].items():
            spec = item["questions"][qid]
            if spec["type"] == "score":
                assert type(gold) is int, (item["id"], qid)
            if spec["type"] == "noul":
                assert type(gold) is bool, (item["id"], qid)
            assert gold in _labels(spec), (item["id"], qid, gold)


def test_each_recipe_asks_one_fixed_question_set() -> None:
    """Questions are weighed jointly, so a recipe's question set must not vary."""
    variants = defaultdict(set)
    for item in ITEMS:
        variants[item["category"]].add(json.dumps(item["questions"], sort_keys=True))
    assert {category: len(v) for category, v in variants.items()} == dict.fromkeys(
        variants, 1
    )


@pytest.mark.parametrize("split", ["dev", "test"])
def test_every_label_appears_in_each_split(split: str) -> None:
    seen = defaultdict(set)
    expected = {}
    for item in ITEMS:
        for qid, gold in item["gold_labels"].items():
            expected[qid] = _labels(item["questions"][qid])
            if item["split"] == split:
                seen[qid].add(gold)
    assert dict(seen) == expected


# ###########################################################################
# Metrics
# ###########################################################################


def test_calibration_error_is_zero_when_confidence_matches_accuracy() -> None:
    ece, mce = metrics.calibration_error([0.75] * 4, [True, True, True, False])
    assert ece == pytest.approx(0.0)
    assert mce == pytest.approx(0.0)


def test_calibration_error_measures_the_gap() -> None:
    ece, _ = metrics.calibration_error([0.8] * 10, [True] * 9 + [False])
    assert ece == pytest.approx(0.1)


def test_brier_scores() -> None:
    assert metrics.brier_multiclass([{"a": 1.0, "b": 0.0}], ["a"]) == pytest.approx(0.0)
    assert metrics.brier_multiclass([{"a": 0.0, "b": 1.0}], ["a"]) == pytest.approx(2.0)
    assert metrics.brier_binary([0.8], [True]) == pytest.approx(0.04)


def test_ranked_probability_score_rewards_near_misses() -> None:
    def rps(probabilities: list[float]) -> float:
        return metrics.ranked_probability_score([probabilities], [0])

    assert rps([1.0, 0.0, 0.0, 0.0]) == pytest.approx(0.0)
    assert rps([0.0, 1.0, 0.0, 0.0]) == pytest.approx(1 / 3)
    assert rps([0.0, 0.0, 0.0, 1.0]) == pytest.approx(1.0)


def test_macro_f1_averages_per_class_scores() -> None:
    # a: tp=1 fp=1 fn=0 -> 2/3; b: tp=0 fp=0 fn=1 -> 0
    assert metrics.macro_f1(["a", "a"], ["a", "b"]) == pytest.approx(1 / 3)


def test_perfect_answers_score_perfectly() -> None:
    summary = metrics.aggregate(
        [metrics.score_item(item, _answers(item, right=True)) for item in ITEMS]
    )
    assert summary["overall"]["questions"] == sum(len(i["gold_labels"]) for i in ITEMS)
    assert summary["overall"]["accuracy"] == 1.0
    assert summary["score"]["mae"] == 0.0
    assert summary["misses"] == []


def test_confident_wrong_noul_answers_are_miscalibrated() -> None:
    """noul calibration is measured against gold, not the model's own prediction."""
    item = next(i for i in ITEMS if i["category"] == "change_risk")
    summary = metrics.aggregate([metrics.score_item(item, _answers(item, right=False))])
    assert summary["noul"]["accuracy"] == 0.0
    assert summary["noul"]["ece"] == pytest.approx(0.9)
    assert summary["noul"]["acting"] == {"n": 1, "coverage": 1.0, "accuracy": 0.0}


def test_noul_score_question_stores_probabilities_and_confidence() -> None:
    item = next(i for i in ITEMS if i["category"] == "change_risk")
    qid = next(qid for qid, s in item["questions"].items() if s["type"] == "noul")
    spec = item["questions"][qid]
    gold = item["gold_labels"][qid]
    record = metrics.score_question(spec, gold, {"type": "noul", "noul": 0.9})
    assert record["probabilities"] == {
        "true": pytest.approx(0.9),
        "false": pytest.approx(0.1),
    }
    assert record["confidence"] == pytest.approx(0.9)
    assert record["p_true"] == pytest.approx(0.9)
    record2 = metrics.score_question(spec, gold, {"type": "noul", "noul": 0.1})
    assert record2["probabilities"] == {
        "true": pytest.approx(0.1),
        "false": pytest.approx(0.9),
    }
    assert record2["confidence"] == pytest.approx(0.9)
    assert record2["probabilities"]["true"] + record2["probabilities"][
        "false"
    ] == pytest.approx(1.0)


def test_a_missing_answer_is_a_contract_error() -> None:
    item = ITEMS[0]
    with pytest.raises(ValueError, match="expected a"):
        metrics.score_item(item, {})


# ###########################################################################
# The eval scripts resolve paths from the checkout root
# ###########################################################################
@pytest.mark.parametrize(
    ("module", "attribute"),
    [
        ("evals.eval.run_evals", "REPO_ROOT"),
        ("evals.eval.report_evals", "REPO_ROOT"),
        ("evals.eval.run_agent_evals", "REPO_ROOT"),
        ("evals.eval.snapshot_evals", "REPO"),
    ],
)
def test_eval_scripts_resolve_the_checkout_root(module, attribute):
    import importlib

    root = getattr(importlib.import_module(module), attribute)
    assert root == Path(__file__).resolve().parents[1]


def test_run_evals_default_dataset_exists():
    from evals.eval import run_evals

    assert run_evals.DATASET_PATH == DATASET


@pytest.mark.parametrize(
    "script",
    [
        "evals/eval/run_evals.py",
        "evals/eval/report_evals.py",
        "evals/eval/snapshot_evals.py",
        "evals/eval/run_agent_evals.py",
        "evals/context/run_context.py",
    ],
)
def test_eval_scripts_run_directly_as_make_runs_them(script):
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(  # noqa: S603 - this interpreter, a repo script, --help
        [sys.executable, str(root / script), "--help"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=root,
    )
    assert result.returncode == 0, result.stderr[-2000:]
