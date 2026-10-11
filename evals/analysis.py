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
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import analysis_design, metrics, report_references, report_text
from .analysis_calibration import confusion, coverage, score_spread
from .analysis_design import option_text
from .analysis_findings import findings
from .analysis_policies import band, bands, misses, policies, signal
from .dataset import protocol

EVALS_DIR = Path(__file__).resolve().parent
Record = dict[str, Any]


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


_ENGINE_LOCATION_KEYS = ("model", "model_dir")


def _public_engine(engine: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``engine`` with any model-location field removed.

    ``Engine.describe()``'s ``model`` field can be a real S3 URI (a hosted
    deployment) and a local run's (undocumented, pre-``describe()``-contract)
    ``model_dir`` can be a real filesystem path carrying the operator's
    username — neither belongs in the published report model (see
    ``meta.deployment_label``, which replaces the raw server URL for the
    same reason). ``device``/``dtype``/the limit fields are all still
    published.

    Parameters
    ----------
    engine : Mapping[str, Any]
        The run's recorded ``engine`` dict.

    Returns
    -------
    dict[str, Any]
        A copy of ``engine`` with ``_ENGINE_LOCATION_KEYS`` removed.
    """
    return {k: v for k, v in engine.items() if k not in _ENGINE_LOCATION_KEYS}


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
                "signal": signal(q),
                "band": band(q),
                "probabilities": q.get("probabilities"),
            }
            if q["type"] == "noul":
                p_true = float(q["p_true"])
                entry["p_true"] = p_true
                entry["confidence"] = (
                    float(q["confidence"])
                    if "confidence" in q
                    else max(p_true, 1.0 - p_true)
                )
            elif q["type"] == "choice":
                entry["confidence"] = float(q["confidence"])
            elif q["type"] == "score":
                entry["abs_error"] = q["abs_error"]
            if qid in specs:
                entry["gold_text"] = option_text(specs[qid], q["gold"])
                entry["predicted_text"] = option_text(specs[qid], q["predicted"])
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
        "protocol": [
            f"{rule.text} *(since dataset version `{rule.since[:12]}`)*"
            for rule in protocol.RULES
        ],
        "datasheet": [(q, a.format(**values)) for q, a in report_text.DATASHEET],
        "metrics": report_text.METRICS,
        "policies": report_text.POLICIES,
        "reliability": report_text.RELIABILITY,
        "limitations": fmt(report_text.LIMITATIONS),
        "reproduce": report_text.REPRODUCE,
        "glossary": report_text.GLOSSARY,
        "references": report_references.REFERENCES,
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
    recipe_rows = analysis_design.recipes(sources)
    composition_model = analysis_design.composition(sources)
    band_table = bands(items)
    policy_rows = policies(items)
    spread = score_spread(items, recipe_rows)
    splits = _splits(trace)
    by_type = {t: (summary[t] or {}).get("n", 0) for t in ("choice", "noul", "score")}
    low, high = summary["overall"]["accuracy_ci"]
    values = {
        "items": len(items),
        "questions": summary["overall"]["questions"],
        **by_type,
        **composition_model["sources"],
        "dev": sum(r["dev"] for r in composition_model["recipes"]),
        "test": sum(r["test"] for r in composition_model["recipes"]),
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
            "engine": _public_engine(config.get("engine") or {}),
            "server_version": config.get("server_version"),
            "host": config.get("host") or {},
            "deployment_label": config.get("deployment_label") or "not recorded",
            "dataset": {
                "name": config["dataset"],
                "file": dataset_path.name,
                "sha256": config["dataset_sha256"],
                "current_sha256": dataset_sha,
                "matches": dataset_sha == config["dataset_sha256"],
                "content_sha256": config.get("dataset_content_sha256"),
            },
            "dataset_content_sha256": config.get("dataset_content_sha256"),
            "recipe_sha256": config.get("recipe_sha256"),
            "register_sha256": config.get("register_sha256"),
            "settings": config.get("settings"),
            "policy": config.get("policy") or {},
            "tokens_available": any(isinstance(t.get("tokens"), dict) for t in trace),
            "split": config.get("split"),
            "category": config.get("category"),
            "n_items": config["n_items"],
            "n_errors": config["n_errors"],
            "results_file": results_path.name,
            "trace_file": trace_name,
        },
        "text": {
            **_text(values),
            "scales": analysis_design.scales_text(recipe_rows),
            "headline_scope": (
                "Headline over coding recipes; vision recipes in the capability panel "
                "(they counted toward the headline before the 2026-10-10 benchmark "
                "foundations, so earlier published headlines are not comparable)."
                if summary.get("capability")
                else "Headline over coding recipes."
            ),
        },
        "summary": summary,
        "card": analysis_design.generated_card(
            dataset_path, config.get("register_sha256"), dataset_sha
        ),
        "findings": findings(summary, band_table, policy_rows, spread, splits, items),
        "composition": composition_model,
        "recipes": recipe_rows,
        "bands": band_table,
        "policies": policy_rows,
        "coverage": coverage(items),
        "confusion": confusion(items, recipe_rows),
        "score_spread": spread,
        "splits": splits,
        "latency": _latency(items, config.get("latency_ms")),
        "items": items,
        "misses": misses(items),
    }
    rounded: Record = metrics.rounded(report)
    return rounded
