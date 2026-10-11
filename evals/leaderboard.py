"""Leaderboard model: one table per dataset version, one row per deployment.

``build(models)`` takes every snapshotted run's report model (``model.json``,
``evals.analysis.build``'s output) and groups the runs by dataset version
(``meta.dataset_content_sha256``; a run from before content hashing forms its
own version under its file hash). Inside a version, runs with the same
``(model, deployment, settings)`` form one row, and each recipe column comes
from the latest run in that group that scored the recipe at the version's
recipe hash, so a partial re-run of one recipe refreshes just that column.
A row's headline is reported only when every headline recipe has a column;
otherwise it is ``None`` and the row is marked ``incomplete``. The site
renders one comparison table per version, newest first; ``rows`` repeats the
newest version's rows for callers that only compare the current dataset.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .dataset.recipes import headline_categories

Record = dict[str, Any]
Model = Mapping[str, Any]

_SETTINGS = ("dtype", "max_length", "max_request_length")


def model_key(meta: Mapping[str, Any]) -> str:
    """Return a model's identity for leaderboard grouping.

    Parameters
    ----------
    meta : Mapping[str, Any]
        A report model's ``meta`` block.

    Returns
    -------
    str
        The registry name (``meta["model_spec"]["name"]``, e.g. ``"flash"``)
        when the run's model matched a registry entry, so a local run
        (``clef-flash``) and a hosted/S3 run (``Cloudflare__clef-flash``) of
        the same model group together. Falls back to the raw ``meta["model"]``
        string for a model outside the registry.
    """
    spec = meta.get("model_spec") or {}
    name = spec.get("name")
    return str(name) if name else str(meta["model"])


def deployment_key(meta: Mapping[str, Any]) -> str:
    """Return a deployment's identity for leaderboard grouping.

    Parameters
    ----------
    meta : Mapping[str, Any]
        A report model's ``meta`` block.

    Returns
    -------
    str
        ``"{deployment_label}|{device}"``: ``meta.deployment_label`` (a
        generic description, e.g. ``"Remote hosted (GPU, CUDA)"``, never
        the raw server URL, which is not published; see
        ``evals.eval.client.deployment_label``) and the engine device
        together identify a deployment, since the same label could in
        principle describe different devices over time, and the same device
        name (e.g. ``cuda``) says nothing about which deployment it was.
    """
    engine = meta.get("engine") or {}
    return f"{meta.get('deployment_label', '?')}|{engine.get('device', '?')}"


def settings_key(meta: Mapping[str, Any]) -> str:
    """Return the engine settings that keep two runs comparable.

    Parameters
    ----------
    meta : Mapping[str, Any]
        A report model's ``meta`` block.

    Returns
    -------
    str
        A canonical JSON rendering of ``meta["settings"]`` (dtype and the two
        length limits). Runs from before the harness recorded ``settings``
        fall back to the same fields of ``meta["engine"]``, so an old and a
        new run of the same deployment still share a row.
    """
    settings = meta.get("settings") or {}
    if not settings:
        engine = meta.get("engine") or {}
        settings = {k: engine.get(k) for k in _SETTINGS}
    return json.dumps(settings, sort_keys=True, default=str)


def version_key(meta: Mapping[str, Any]) -> str:
    """Return the dataset version a run was scored on.

    Parameters
    ----------
    meta : Mapping[str, Any]
        A report model's ``meta`` block.

    Returns
    -------
    str
        ``meta["dataset_content_sha256"]`` when the run recorded one; else
        the dataset's file hash, so runs from before content hashing form
        their own version and never merge with content-hashed runs.
    """
    content = meta.get("dataset_content_sha256")
    if content:
        return str(content)
    dataset = meta.get("dataset") or {}
    return str(dataset.get("sha256") or "unversioned")


def _identity(meta: Mapping[str, Any]) -> Record:
    spec = meta.get("model_spec") or {}
    engine = meta.get("engine") or {}
    host = meta.get("host") or {}
    return {
        "model_key": model_key(meta),
        "model_name": meta["model"],
        "model_repo": spec.get("repo"),
        "params": spec.get("params"),
        "deployment_key": deployment_key(meta),
        "deployment_label": meta.get("deployment_label"),
        "settings_key": settings_key(meta),
        "device": engine.get("device"),
        "dtype": engine.get("dtype"),
        "ember_server_version": meta.get("server_version"),
        "ember_client_version": host.get("packages", {}).get("ember-advise"),
    }


def _overall(overall: Mapping[str, Any]) -> Record:
    return {
        "accuracy": overall["accuracy"],
        "accuracy_ci": overall.get("accuracy_ci"),
        "item_accuracy": overall["item_accuracy"],
        "items": overall["items"],
        "questions": overall["questions"],
    }


def _version_hashes(runs: Iterable[Model]) -> dict[str, str]:
    """Return each recipe's hash on this version; the newest run's record wins."""
    hashes: dict[str, str] = {}
    for run in sorted(runs, key=lambda run: str(run["meta"]["run_at"]), reverse=True):
        for category, digest in (run["meta"].get("recipe_sha256") or {}).items():
            hashes.setdefault(category, str(digest))
    return hashes


def _recipe_columns(group: Sequence[Model], hashes: Mapping[str, str]) -> Record:
    columns: Record = {}
    for category, digest in hashes.items():
        for run in group:
            meta = run["meta"]
            scored = (run["summary"].get("categories") or {}).get(category)
            if scored and (meta.get("recipe_sha256") or {}).get(category) == digest:
                columns[category] = {
                    "accuracy": scored["accuracy"],
                    "item_accuracy": scored["item_accuracy"],
                    "items": scored["items"],
                    "recipe_sha256": digest,
                    "run_id": meta["run_id"],
                    "run_at": meta["run_at"],
                }
                break
    return columns


def _assembled_headline(
    columns: Mapping[str, Record], group: Sequence[Model]
) -> Record:
    """Combine the headline recipes' columns into one accuracy figure.

    When every column comes from the same run, that run's ``overall`` block is
    reported as-is (with its interval). Columns from several runs are pooled
    by question count; no interval is reported for a pooled figure.
    """
    headline = headline_categories()
    producers = {columns[c]["run_id"] for c in headline}
    by_id = {run["meta"]["run_id"]: run for run in group}
    if len(producers) == 1:
        return _overall(by_id[producers.pop()]["summary"]["overall"])
    questions = correct = items = items_correct = 0.0
    for category in headline:
        run = by_id[columns[category]["run_id"]]
        for question in (run["summary"].get("questions") or {}).values():
            if question.get("category") == category:
                questions += question["n"]
                correct += question["n"] * question["accuracy"]
        items += columns[category]["items"]
        items_correct += columns[category]["items"] * columns[category]["item_accuracy"]
    return {
        "accuracy": round(correct / questions, 4) if questions else None,
        "accuracy_ci": None,
        "item_accuracy": round(items_correct / items, 4) if items else None,
        "items": int(items),
        "questions": int(questions),
    }


def _tiers(summary: Mapping[str, Any]) -> Record | None:
    tiers = summary.get("tiers")
    if not tiers:
        return None
    non_easy = tiers.get("non_easy") or {}
    return {"non_easy_accuracy": non_easy.get("accuracy")}


def _row(group: Sequence[Model], hashes: Mapping[str, str], version: str) -> Record:
    """Build one row from a group's runs (newest first) on one dataset version."""
    newest = group[0]
    meta, summary = newest["meta"], newest["summary"]
    if meta.get("recipe_sha256"):
        columns = _recipe_columns(group, hashes)
        incomplete = any(c not in columns for c in headline_categories())
        headline = None if incomplete else _assembled_headline(columns, group)
        contributing = {column["run_id"] for column in columns.values()} or {
            meta["run_id"]
        }
        newest = max(
            (run for run in group if run["meta"]["run_id"] in contributing),
            key=lambda run: run["meta"]["run_at"],
        )
        meta, summary = newest["meta"], newest["summary"]
    else:
        columns, incomplete, headline = {}, False, _overall(summary["overall"])
    latency = newest.get("latency") or {}
    numbers = headline or dict.fromkeys(_overall(summary["overall"]))
    return {
        "run_id": meta["run_id"],
        "run_at": meta["run_at"],
        **_identity(meta),
        **numbers,
        "latency_p50": latency.get("p50"),
        "latency_p95": latency.get("p95"),
        "dataset_content_sha256": version,
        "headline": headline,
        "incomplete": incomplete,
        "recipes": columns,
        "capability": summary.get("capability"),
        "risk": summary.get("risk") or {},
        "tiers": _tiers(summary),
        "single_rater": True,
    }


def _rows(version: str, runs: Sequence[Model]) -> list[Record]:
    groups: dict[tuple[str, str, str], list[Model]] = defaultdict(list)
    for run in sorted(runs, key=lambda run: run["meta"]["run_at"], reverse=True):
        meta = run["meta"]
        groups[model_key(meta), deployment_key(meta), settings_key(meta)].append(run)
    hashes = _version_hashes(run for group in groups.values() for run in group)
    rows = [_row(group, hashes, version) for group in groups.values()]
    rows.sort(
        key=lambda row: (
            row["accuracy"] if row["accuracy"] is not None else -1.0,
            row["run_at"],
        ),
        reverse=True,
    )
    return rows


def build(models: Sequence[Model]) -> Record:
    """Build the leaderboard: one table per dataset version, one row per group.

    Parameters
    ----------
    models : Sequence[Mapping[str, Any]]
        Every snapshotted run's report model (``evals.analysis.build``'s
        output, as read back from ``benchmark/<run-id>/model.json``).

    Returns
    -------
    dict[str, Any]
        ``{"versions": [...], "rows": [...]}``. Each version carries its
        ``dataset_content_sha256``, ``newest`` flag, the ``run_at`` of its
        latest run, and ``rows`` sorted by headline accuracy, descending,
        incomplete rows last. A row carries model/deployment/settings
        identity, the ``headline`` (``None`` while ``incomplete``), one
        ``recipes[category]`` column per scored recipe naming the producing
        run, ``capability``, ``risk``, ``tiers``, latency, and version
        provenance. ``rows`` repeats the newest version's rows.
    """
    by_version: dict[str, list[Model]] = defaultdict(list)
    for model in models:
        by_version[version_key(model["meta"])].append(model)
    versions = [
        {
            "dataset_content_sha256": version,
            "newest": False,
            "run_at": max(run["meta"]["run_at"] for run in runs),
            "rows": _rows(version, runs),
        }
        for version, runs in by_version.items()
    ]
    versions.sort(key=lambda version: str(version["run_at"]), reverse=True)
    if versions:
        versions[0]["newest"] = True
    return {"versions": versions, "rows": versions[0]["rows"] if versions else []}
