"""Report model for the ember benchmark: everything a report shows, computed once.

``build(results_path)`` reads a run's results and trace, joins each item's state
and rationale from the dataset, and returns one JSON-serialisable dict that the
Markdown and HTML renderers share. Tables, chart series, decision outcomes, and
findings all live here, so the renderers only present them.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import metrics, report_text
from .render.tone import Tone

EVALS_DIR = Path(__file__).resolve().parent
Record = dict[str, Any]

# Decision rules from ember/agent_kit (instructions.md, SKILL.md, AGENTS.snippet.md).
TRUST = metrics.CHOICE_TRUST
VERIFY = 0.60
CLARIFY_AT = 0.20
REVIEW_P = 0.80
REVIEW_RISK = 2.0


def _read_jsonl(path: Path) -> list[Record]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def dataset_for(results_path: Path, dataset: Mapping[str, Any]) -> Path:
    """Resolve the dataset a run scored.

    Prefer the snapshot stored beside the run (``dataset_file``), so a report
    reflects the bytes actually scored even if the checkout's dataset changed;
    fall back to the dataset in this checkout for runs recorded before
    snapshots existed.
    """
    recorded = dataset.get("file")
    if recorded:
        beside = results_path.with_name(str(recorded))
        if beside.exists():
            return beside
    return EVALS_DIR / str(dataset["name"])


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _signal(question: Mapping[str, Any]) -> float:
    key = {"choice": "confidence", "noul": "p_true", "score": "expected"}
    return float(question[key[question["type"]]])


def _band(question: Mapping[str, Any]) -> str | None:
    if question["type"] == "choice":
        confidence = float(question["confidence"])
        return (
            "trust"
            if confidence >= TRUST
            else "verify"
            if confidence >= VERIFY
            else "defer"
        )
    if question["type"] == "noul":
        p_true = float(question["p_true"])
        return (
            "yes"
            if p_true >= metrics.NOUL_YES
            else "no"
            if p_true <= metrics.NOUL_NO
            else "unsure"
        )
    return None


def _option_text(spec: Mapping[str, Any], label: Any) -> str:
    criteria = spec.get("criteria")
    if spec["type"] == "noul":
        key = "true" if label else "false"
        return str(criteria[key]) if criteria else ("yes" if label else "no")
    return str(criteria[label])


def _label_order(spec: Mapping[str, Any]) -> list[Any]:
    if spec["type"] == "noul":
        return [True, False]
    if spec["type"] == "score":
        return list(range(len(spec["criteria"])))
    return list(spec["criteria"])


# ###########################################################################
# Items and question sets
# ###########################################################################


def _items(trace: Sequence[Record], dataset: Mapping[str, Record]) -> list[Record]:
    items = []
    for scored in trace:
        source = dataset.get(scored["id"], {})
        specs = source.get("questions", {})
        questions = {}
        for qid, q in scored["questions"].items():
            entry: Record = {
                "type": q["type"],
                "gold": q["gold"],
                "predicted": q["predicted"],
                "correct": q["correct"],
                "signal": _signal(q),
                "band": _band(q),
                "probabilities": q.get("probabilities"),
            }
            if q["type"] == "noul":
                p_true = float(q["p_true"])
                entry["p_true"] = p_true
                entry["confidence"] = float(q["confidence"]) if "confidence" in q else max(p_true, 1.0 - p_true)
            elif q["type"] == "choice":
                entry["confidence"] = float(q["confidence"])
            elif q["type"] == "score":
                entry["abs_error"] = q["abs_error"]
            if qid in specs:
                entry["gold_text"] = _option_text(specs[qid], q["gold"])
                entry["predicted_text"] = _option_text(specs[qid], q["predicted"])
            questions[qid] = entry
        items.append(
            {
                "id": scored["id"],
                "category": scored["category"],
                "split": scored["split"],
                "source": source.get("source"),
                "state": source.get("state"),
                "rationale": source.get("rationale"),
                "correct": scored["correct"],
                "latency_ms": scored.get("latency_ms"),
                "questions": questions,
            }
        )
    return items


def _recipes(sources: Sequence[Record]) -> list[Record]:
    first: dict[str, Record] = {}
    for item in sources:
        first.setdefault(item["category"], item)
    recipes = []
    for category, item in first.items():
        questions = []
        for qid, spec in item["questions"].items():
            criteria = spec.get("criteria")
            if isinstance(criteria, dict):
                options = [{"label": k, "text": v} for k, v in criteria.items()]
            elif isinstance(criteria, list):
                options = [{"label": i, "text": v} for i, v in enumerate(criteria)]
            else:
                options = []
            questions.append(
                {
                    "id": qid,
                    "type": spec["type"],
                    "instructions": spec["instructions"],
                    "options": options,
                }
            )
        recipes.append(
            {
                "category": category,
                **report_text.RECIPES.get(category, {}),
                "questions": questions,
            }
        )
    return recipes


def _composition(sources: Sequence[Record]) -> Record:
    recipes: dict[str, Record] = {}
    labels: dict[str, Record] = {}
    for item in sources:
        row = recipes.setdefault(
            item["category"],
            {
                "category": item["category"],
                "title": report_text.RECIPES.get(item["category"], {}).get(
                    "title", item["category"]
                ),
                "items": 0,
                "dev": 0,
                "test": 0,
                "questions": list(item["questions"]),
            },
        )
        row["items"] += 1
        row[item["split"]] += 1
        for qid, gold in item["gold_labels"].items():
            spec = item["questions"][qid]
            entry = labels.setdefault(
                qid, {"type": spec["type"], "spec": spec, "counts": {}}
            )
            counts = entry["counts"].setdefault(
                json.dumps(gold),
                {"label": gold, "text": _option_text(spec, gold), "dev": 0, "test": 0},
            )
            counts[item["split"]] += 1
    for entry in labels.values():
        order = [json.dumps(label) for label in _label_order(entry.pop("spec"))]
        counts = entry.pop("counts")
        entry["labels"] = [counts[key] for key in order if key in counts]
    sources_count = {
        "skill_md": sum(1 for i in sources if i.get("source") == "skill_md"),
        "curated": sum(1 for i in sources if i.get("source") != "skill_md"),
    }
    return {
        "recipes": list(recipes.values()),
        "labels": labels,
        "sources": sources_count,
    }


# ###########################################################################
# Calibration, confusion, and score spread
# ###########################################################################


def _questions_of(items: Sequence[Record], qtype: str) -> list[Record]:
    return [
        {**q, "question": qid, "id": item["id"]}
        for item in items
        for qid, q in item["questions"].items()
        if q["type"] == qtype
    ]


def _confidence(question: Mapping[str, Any]) -> float:
    if question["type"] == "noul":
        return max(question["signal"], 1.0 - question["signal"])
    return float(question["signal"])


def _coverage(items: Sequence[Record]) -> Record:
    curves: Record = {}
    kit = {
        "choice": [
            {"threshold": TRUST, "label": "trust"},
            {"threshold": VERIFY, "label": "verify"},
        ],
        "noul": [{"threshold": metrics.NOUL_YES, "label": "decisive"}],
    }
    for qtype in ("choice", "noul"):
        answers = [
            (_confidence(q), bool(q["correct"])) for q in _questions_of(items, qtype)
        ]
        points = []
        for step in range(101):
            threshold = step / 100
            kept = [ok for confidence, ok in answers if confidence >= threshold]
            if kept:
                points.append(
                    {
                        "threshold": threshold,
                        "coverage": len(kept) / len(answers),
                        "accuracy": sum(kept) / len(kept),
                        "n": len(kept),
                    }
                )
        curves[qtype] = {"points": points, "kit": kit[qtype]}
    return curves


def _confusion(items: Sequence[Record], recipes: Sequence[Record]) -> Record:
    specs = {q["id"]: q for recipe in recipes for q in recipe["questions"]}
    matrices: Record = {}
    for qid, spec in specs.items():
        if spec["type"] == "noul":
            labels: list[Any] = [True, False]
            names = ["yes", "no"]
        else:
            labels = [option["label"] for option in spec["options"]]
            names = [
                str(option["label"]) if spec["type"] == "choice" else option["text"]
                for option in spec["options"]
            ]
        index = {json.dumps(label): i for i, label in enumerate(labels)}
        matrix = [[0] * len(labels) for _ in labels]
        for item in items:
            question = item["questions"].get(qid)
            if question is not None:
                matrix[index[json.dumps(question["gold"])]][
                    index[json.dumps(question["predicted"])]
                ] += 1
        matrices[qid] = {
            "type": spec["type"],
            "labels": names,
            "matrix": matrix,
            "rows": "gold",
            "columns": "predicted",
        }
    return matrices


def _score_spread(items: Sequence[Record], recipes: Sequence[Record]) -> Record:
    spread: Record = {}
    for recipe in recipes:
        for spec in recipe["questions"]:
            if spec["type"] != "score":
                continue
            levels = [option["text"] for option in spec["options"]]
            points = [
                {
                    "id": item["id"],
                    "split": item["split"],
                    "gold": q["gold"],
                    "expected": q["signal"],
                    "correct": q["correct"],
                }
                for item in items
                if (q := item["questions"].get(spec["id"])) is not None
            ]
            means = []
            for level, label in enumerate(levels):
                values = [p["expected"] for p in points if p["gold"] == level]
                means.append(
                    {
                        "level": level,
                        "label": label,
                        "n": len(values),
                        "mean_expected": sum(values) / len(values) if values else None,
                    }
                )
            spread[spec["id"]] = {"levels": levels, "points": points, "means": means}
    return spread


# ###########################################################################
# Decision rules: confidence bands and the default project policy
# ###########################################################################

BANDS = {
    "choice": [
        ("trust", "confidence >= 0.85", "act on it"),
        ("verify", "0.60 <= confidence < 0.85", "act, say so, and verify"),
        ("defer", "confidence < 0.60", "gather evidence or ask the user"),
    ],
    "noul": [
        ("yes", "P >= 0.80", "treat as yes"),
        ("no", "P <= 0.20", "treat as no"),
        ("unsure", "0.20 < P < 0.80", "treat as unsure"),
    ],
}


def _bands(items: Sequence[Record]) -> Record:
    table: Record = {}
    for qtype, rows in BANDS.items():
        answers = _questions_of(items, qtype)
        table[qtype] = []
        for band, rule, action in rows:
            members = [q for q in answers if q["band"] == band]
            correct = sum(bool(q["correct"]) for q in members)
            table[qtype].append(
                {
                    "band": band,
                    "rule": rule,
                    "action": action,
                    "n": len(members),
                    "share": len(members) / len(answers) if answers else 0.0,
                    "correct": correct,
                    "accuracy": correct / len(members) if members else None,
                }
            )
    return table


def _policy(
    items: Sequence[Record],
    *,
    key: str,
    title: str,
    rule: str,
    extra: str,
    wrong: str,
    decide: Callable[[Mapping[str, Any]], bool],
    expect: Callable[[Mapping[str, Any]], bool],
) -> Record:
    rows = []
    for item in items:
        did, should = decide(item["questions"]), expect(item["questions"])
        outcome = "right" if did == should else "extra_step" if did else "wrong_action"
        rows.append(
            {
                "id": item["id"],
                "acted": did,
                "should": should,
                "outcome": outcome,
                "signals": {k: v["signal"] for k, v in item["questions"].items()},
            }
        )
    return {
        "key": key,
        "title": title,
        "rule": rule,
        "n": len(rows),
        "right": sum(r["outcome"] == "right" for r in rows),
        "extra_step": sum(r["outcome"] == "extra_step" for r in rows),
        "wrong_action": sum(r["outcome"] == "wrong_action" for r in rows),
        "extra_label": extra,
        "wrong_label": wrong,
        "cases": [r for r in rows if r["outcome"] != "right"],
    }


def _policies(items: Sequence[Record]) -> list[Record]:
    policies = []
    intent = [i for i in items if "specific_enough" in i["questions"]]
    if intent:
        policies.append(
            _policy(
                intent,
                key="clarify",
                title="Clarify vague requests",
                rule="Ask a clarifying question when specific_enough <= 0.20.",
                extra="asked an unnecessary question",
                wrong="acted on a vague request",
                decide=lambda q: q["specific_enough"]["signal"] <= CLARIFY_AT,
                expect=lambda q: not q["specific_enough"]["gold"],
            )
        )
    risky = [i for i in items if {"risk", "needs_review"} <= set(i["questions"])]
    if risky:
        policies.append(
            _policy(
                risky,
                key="review",
                title="Stop risky changes for review",
                rule="Stop and request review when needs_review >= 0.80 "
                "or risk >= 2.0 of 3.",
                extra="requested an unnecessary review",
                wrong="shipped a risky change unreviewed",
                decide=lambda q: (
                    q["needs_review"]["signal"] >= REVIEW_P
                    or q["risk"]["signal"] >= REVIEW_RISK
                ),
                expect=lambda q: q["risk"]["gold"] >= 2,
            )
        )
    return policies


def _misses(items: Sequence[Record]) -> list[Record]:
    outcome = {
        "trust": "acted on a wrong answer",
        "yes": "acted on a wrong answer",
        "no": "acted on a wrong answer",
        "verify": "acted, flagged for verification",
        "defer": "deferred: gather evidence or ask",
        "unsure": "deferred: treated as unsure",
    }
    misses = []
    for item in items:
        for qid, q in item["questions"].items():
            if q["correct"]:
                continue
            kit = outcome.get(q["band"] or "", "missed the exact level")
            if q["type"] == "score" and q["abs_error"] <= 1.0:
                kit = "within one level of gold"
            misses.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "split": item["split"],
                    "question": qid,
                    **{k: v for k, v in q.items() if k != "correct"},
                    "kit_outcome": kit,
                    "state": item["state"],
                    "rationale": item["rationale"],
                }
            )
    return misses


# ###########################################################################
# Splits, latency, findings
# ###########################################################################


def _splits(trace: Sequence[Record]) -> Record:
    splits: Record = {}
    for split in ("dev", "test"):
        subset = [t for t in trace if t["split"] == split]
        if not subset:
            continue
        summary = metrics.aggregate(subset)
        splits[split] = {
            **summary["overall"],
            "by_type": {
                t: summary[t]["accuracy"]
                for t in ("choice", "noul", "score")
                if summary[t]
            },
            "score_mae": summary["score"]["mae"] if summary["score"] else None,
        }
    return splits


def _latency(items: Sequence[Record], stats: Mapping[str, Any] | None) -> Record:
    by_category: dict[str, list[float]] = defaultdict(list)
    for item in items:
        if item["latency_ms"] is not None:
            by_category[item["category"]].append(float(item["latency_ms"]))
    return {
        "values": [v for values in by_category.values() for v in values],
        "by_category": {c: sum(v) / len(v) for c, v in by_category.items()},
        **(stats or {}),
    }


def _findings(
    summary: Mapping[str, Any],
    bands: Mapping[str, Any],
    policies: Sequence[Record],
    spread: Mapping[str, Any],
    splits: Mapping[str, Any],
    items: Sequence[Record],
) -> list[Record]:
    findings: list[Record] = []
    overall = summary["overall"]
    low, high = overall["accuracy_ci"]
    findings.append(
        {
            "tone": Tone.INFO,
            "title": "Overall accuracy",
            "text": f"{_pct(overall['accuracy'])} of {overall['questions']} "
            "questions were "
            f"answered correctly (95% CI {_pct(low)} to {_pct(high)}), and "
            f"{_pct(overall['item_accuracy'])} of {overall['items']} items had every "
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
                f"correct ({_pct(right / acted)}).",
            }
        )

    choice_misses = [q for q in _questions_of(items, "choice") if not q["correct"]]
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
        answers = _questions_of(items, qtype)
        if not answers:
            continue
        mean_conf = sum(_confidence(q) for q in answers) / len(answers)
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
                f"{mean_conf:.2f} against {_pct(accuracy)} accuracy (ECE "
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
                "text": f"{strong} is strongest at {_pct(s['accuracy'])}; "
                f"{weak} is weakest at "
                f"{_pct(w['accuracy'])}.",
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
                "text": f"dev scored {_pct(dev['accuracy'])} and test "
                f"{_pct(test['accuracy'])}; "
                + (
                    "their 95% intervals overlap."
                    if overlap
                    else "their 95% intervals do not overlap."
                ),
            }
        )
    return findings


# ###########################################################################
# Build
# ###########################################################################


def _text(values: Mapping[str, Any]) -> Record:
    def fmt(paragraphs: Sequence[str]) -> list[str]:
        return [p.format(**values) for p in paragraphs]

    return {
        "title": report_text.TITLE,
        "subtitle": report_text.SUBTITLE,
        "context": report_text.CONTEXT,
        "question_types": report_text.QUESTION_TYPES,
        "system": report_text.SYSTEM,
        "architecture": report_text.ARCHITECTURE,
        "architecture_text": report_text.ARCHITECTURE_TEXT,
        "dataset": fmt(report_text.DATASET),
        "protocol": report_text.PROTOCOL,
        "datasheet": [(q, a.format(**values)) for q, a in report_text.DATASHEET],
        "metrics": report_text.METRICS,
        "policies": report_text.POLICIES,
        "reliability": report_text.RELIABILITY,
        "limitations": fmt(report_text.LIMITATIONS),
        "reproduce": report_text.REPRODUCE,
        "glossary": report_text.GLOSSARY,
        "references": report_text.REFERENCES,
    }


def build(results_path: Path, *, dataset_path: Path | None = None) -> Record:
    """Build the full report model for one run's ``*_results.json``."""
    data = json.loads(results_path.read_text(encoding="utf-8"))
    config, summary = data["config"], data["summary"]
    trace_name = config.get("trace") or results_path.name.replace(
        "_results.json", "_trace.jsonl"
    )
    trace = _read_jsonl(results_path.with_name(trace_name))
    dataset_path = dataset_path or dataset_for(
        results_path, {"name": config["dataset"], "file": config.get("dataset_file")}
    )
    dataset_sha = (
        hashlib.sha256(dataset_path.read_bytes()).hexdigest()
        if dataset_path.exists()
        else None
    )
    dataset = (
        {item["id"]: item for item in _read_jsonl(dataset_path)}
        if dataset_path.exists()
        else {}
    )
    sources = [dataset[t["id"]] for t in trace if t["id"] in dataset]

    items = _items(trace, dataset)
    recipes = _recipes(sources)
    composition = _composition(sources)
    bands = _bands(items)
    policies = _policies(items)
    spread = _score_spread(items, recipes)
    splits = _splits(trace)
    by_type = {t: (summary[t] or {}).get("n", 0) for t in ("choice", "noul", "score")}
    low, high = summary["overall"]["accuracy_ci"]
    values = {
        "items": len(items),
        "questions": summary["overall"]["questions"],
        **by_type,
        **composition["sources"],
        "dev": sum(r["dev"] for r in composition["recipes"]),
        "test": sum(r["test"] for r in composition["recipes"]),
        "ci_width": f"{(high - low) * 100:.0f}",
    }
    timestamp = datetime.strptime(config["timestamp"], "%Y%m%dT%H%M%SZ").replace(
        tzinfo=UTC
    )
    report: Record = {
        "meta": {
            "run_id": config["run_id"],
            "run_at": timestamp.strftime("%Y-%m-%d %H:%M UTC"),
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "git_hash": config["git_hash"],
            "model": config["model"],
            "model_spec": config.get("model_spec") or {},
            "engine": config.get("engine") or {},
            "host": config.get("host") or {},
            "server": config.get("server"),
            "dataset": {
                "name": config["dataset"],
                "file": dataset_path.name,
                "sha256": config["dataset_sha256"],
                "current_sha256": dataset_sha,
                "matches": dataset_sha == config["dataset_sha256"],
            },
            "split": config.get("split"),
            "category": config.get("category"),
            "n_items": config["n_items"],
            "n_errors": config["n_errors"],
            "results_file": results_path.name,
            "trace_file": trace_name,
        },
        "text": _text(values),
        "summary": summary,
        "findings": _findings(summary, bands, policies, spread, splits, items),
        "composition": composition,
        "recipes": recipes,
        "bands": bands,
        "policies": policies,
        "coverage": _coverage(items),
        "confusion": _confusion(items, recipes),
        "score_spread": spread,
        "splits": splits,
        "latency": _latency(items, config.get("latency_ms")),
        "items": items,
        "misses": _misses(items),
    }
    rounded: Record = metrics.rounded(report)
    return rounded
