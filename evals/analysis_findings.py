"""The report's findings: one-line observations with a tone, computed from the summary.

Split out of ``evals/analysis.py`` (Article X §10.3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .render.tone import Tone

Record = dict[str, Any]


def pct(value: float) -> str:
    """Format a ratio as a percentage with one decimal."""
    return f"{value * 100:.1f}%"


def questions_of(items: Sequence[Record], qtype: str) -> list[Record]:
    """Return every scored question of type ``qtype`` with its item id."""
    return [
        {**q, "question": qid, "id": item["id"]}
        for item in items
        for qid, q in item["questions"].items()
        if q["type"] == qtype
    ]


def confidence(question: Mapping[str, Any]) -> float:
    """Return the top-label confidence of a scored question."""
    if question["type"] == "noul":
        return max(question["signal"], 1.0 - question["signal"])
    return float(question["signal"])


def findings(
    summary: Mapping[str, Any],
    bands: Mapping[str, Any],
    policies: Sequence[Record],
    spread: Mapping[str, Any],
    splits: Mapping[str, Any],
    items: Sequence[Record],
) -> list[Record]:
    """Return the report's findings, each with a tone and a one-line text."""
    findings: list[Record] = []
    overall = summary["overall"]
    low, high = overall["accuracy_ci"]
    findings.append(
        {
            "tone": Tone.INFO,
            "title": "Overall accuracy",
            "text": f"{pct(overall['accuracy'])} of {overall['questions']} "
            "questions were "
            f"answered correctly (95% CI {pct(low)} to {pct(high)}), and "
            f"{pct(overall['item_accuracy'])} of {overall['items']} items had every "
            "question right.",
        }
    )

    acting = [row for row in bands.get("choice", []) if row["band"] == "trust"]
    acting += [row for row in bands.get("noul", []) if row["band"] in ("yes", "no")]
    acted = sum(row["n"] for row in acting)
    if acted:
        right = sum(row["correct"] for row in acting)
        findings.append(
            {
                "tone": Tone.GOOD if right == acted else Tone.WARN,
                "title": "Answers past the kit's thresholds",
                "text": f"{right} of {acted} answers that cleared the kit's act-on-it "
                "thresholds (choice confidence >= 0.85; noul P >= 0.80 or "
                "<= 0.20) were "
                f"correct ({pct(right / acted)}).",
            }
        )

    choice_misses = [q for q in questions_of(items, "choice") if not q["correct"]]
    if choice_misses:
        top = max(choice_misses, key=lambda q: q["signal"])
        trusted = sum(q["band"] == "trust" for q in choice_misses)
        findings.append(
            {
                "tone": Tone.GOOD if trusted == 0 else Tone.WARN,
                "title": "Where the choice misses fell",
                "text": f"{trusted} of {len(choice_misses)} choice misses cleared "
                f"the 0.85 trust line; the most confident miss ({top['id']}, "
                f"{top['question']}) had "
                f"confidence {top['signal']:.2f}.",
            }
        )

    for policy in policies:
        wrong, extra = policy["wrong_action"], policy["extra_step"]
        cases = ", ".join(
            c["id"] for c in policy["cases"] if c["outcome"] == "wrong_action"
        )
        text = (
            f"Following '{policy['rule']}' on {policy['n']} items, an agent "
            f"would have {policy['wrong_label']} {wrong} times"
        )
        text += f" ({cases})" if cases else ""
        text += f" and {policy['extra_label']} {extra} times."
        findings.append(
            {
                "tone": Tone.WARN if wrong else Tone.GOOD,
                "title": policy["title"],
                "text": text,
            }
        )

    for qtype, label in (("choice", "choice"), ("noul", "noul")):
        answers = questions_of(items, qtype)
        if not answers:
            continue
        mean_conf = sum(confidence(q) for q in answers) / len(answers)
        accuracy = sum(bool(q["correct"]) for q in answers) / len(answers)
        gap = accuracy - mean_conf
        direction = (
            "under-confident"
            if gap > 0.05
            else "over-confident"
            if gap < -0.05
            else "calibrated on average"
        )
        findings.append(
            {
                "tone": Tone.WARN if gap < -0.05 else Tone.INFO,
                "title": f"{label} calibration",
                "text": f"{label} answers are {direction}: mean top-label confidence "
                f"{mean_conf:.2f} against {pct(accuracy)} accuracy (ECE "
                f"{summary[qtype]['ece']:.3f}).",
            }
        )

    for qid, entry in spread.items():
        means = [m for m in entry["means"] if m["mean_expected"] is not None]
        if len(means) < 2:
            continue
        lowest, highest = means[0], means[-1]
        top_level = len(entry["levels"]) - 1
        if (
            lowest["mean_expected"] - lowest["level"] > 0.3
            and highest["level"] - highest["mean_expected"] > 0.3
        ):
            findings.append(
                {
                    "tone": Tone.INFO,
                    "title": f"{qid} answers shrink toward the middle",
                    "text": f"On the 0 to {top_level} scale, gold "
                    f"'{lowest['label']}' items average "
                    f"{lowest['mean_expected']:.2f} and gold '{highest['label']}' "
                    f"items average {highest['mean_expected']:.2f}. Thresholds on the "
                    "expected score work better than rounding it to a level.",
                }
            )

    questions = summary["questions"]
    if questions:
        ranked = sorted(questions.items(), key=lambda kv: kv[1]["accuracy"])
        (weak, w), (strong, s) = ranked[0], ranked[-1]
        findings.append(
            {
                "tone": Tone.INFO,
                "title": "Strongest and weakest questions",
                "text": f"{strong} is strongest at {pct(s['accuracy'])}; "
                f"{weak} is weakest at "
                f"{pct(w['accuracy'])}.",
            }
        )

    if {"dev", "test"} <= set(splits):
        dev, test = splits["dev"], splits["test"]
        overlap = (
            dev["accuracy_ci"][0] <= test["accuracy_ci"][1]
            and test["accuracy_ci"][0] <= dev["accuracy_ci"][1]
        )
        findings.append(
            {
                "tone": Tone.INFO if overlap else Tone.WARN,
                "title": "dev and test agree" if overlap else "dev and test differ",
                "text": f"dev scored {pct(dev['accuracy'])} and test "
                f"{pct(test['accuracy'])}; "
                + (
                    "their 95% intervals overlap."
                    if overlap
                    else "their 95% intervals do not overlap."
                ),
            }
        )
    return findings
