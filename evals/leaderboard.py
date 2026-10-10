"""Leaderboard model: group tracked benchmark runs by model and deployment.

``build(models)`` takes every snapshotted run's report model (``model.json``,
``evals.analysis.build``'s output) and returns one row per distinct
``(model, deployment)`` pair, keeping only the latest run when a pair has
been re-run. The site renders this as a comparison table across models
(``flash``, ``full``, future registry entries) and deployments (local MPS,
a hosted CUDA endpoint, and so on), alongside the existing single-run report
pages.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

Record = dict[str, Any]


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
        ``"{server}|{device}"``: the server URL and the engine device
        together identify a deployment, since the same server URL could in
        principle serve different devices over time, and the same device
        name (e.g. ``cuda``) says nothing about which deployment it was.
    """
    engine = meta.get("engine") or {}
    return f"{meta.get('server', '?')}|{engine.get('device', '?')}"


def _row(
    meta: Mapping[str, Any], summary: Mapping[str, Any], latency: Mapping[str, Any]
) -> Record:
    spec = meta.get("model_spec") or {}
    engine = meta.get("engine") or {}
    host = meta.get("host") or {}
    overall = summary["overall"]
    return {
        "run_id": meta["run_id"],
        "run_at": meta["run_at"],
        "model_key": model_key(meta),
        "model_name": meta["model"],
        "model_repo": spec.get("repo"),
        "params": spec.get("params"),
        "deployment_key": deployment_key(meta),
        "server": meta.get("server"),
        "device": engine.get("device"),
        "dtype": engine.get("dtype"),
        "ember_server_version": meta.get("server_version"),
        "ember_client_version": host.get("packages", {}).get("ember-advise"),
        "accuracy": overall["accuracy"],
        "accuracy_ci": overall["accuracy_ci"],
        "item_accuracy": overall["item_accuracy"],
        "items": overall["items"],
        "questions": overall["questions"],
        "latency_p50": latency.get("p50"),
        "latency_p95": latency.get("p95"),
    }


def build(models: Sequence[Mapping[str, Any]]) -> Record:
    """Build the leaderboard: one row per ``(model, deployment)``, latest run only.

    Parameters
    ----------
    models : Sequence[Mapping[str, Any]]
        Every snapshotted run's report model (``evals.analysis.build``'s
        output, as read back from ``benchmark/<run-id>/model.json``).

    Returns
    -------
    dict[str, Any]
        ``{"rows": [...]}``: rows sorted by accuracy, descending. Each row
        carries the fields a comparison table needs: model/deployment
        identity, accuracy and its CI, item accuracy, latency, and version
        provenance (``ember_server_version``, ``ember_client_version``).
    """
    latest: dict[tuple[str, str], Mapping[str, Any]] = {}
    for model in models:
        meta = model["meta"]
        group = (model_key(meta), deployment_key(meta))
        current = latest.get(group)
        if current is None or meta["run_at"] > current["meta"]["run_at"]:
            latest[group] = model
    rows = [
        _row(m["meta"], m["summary"], m.get("latency") or {}) for m in latest.values()
    ]
    rows.sort(key=lambda row: row["accuracy"], reverse=True)
    return {"rows": rows}
