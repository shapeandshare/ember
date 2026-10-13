#!/usr/bin/env python3
"""Render every tracked benchmark bundle into the Jekyll site.

Reads every ``benchmark/<run-id>/model.json``, groups them into a leaderboard
(``evals.leaderboard.build``: one table per dataset version, one row per
model, deployment, and settings, each recipe column from the latest run that
scored it), and writes native site pages under ``site/results/`` (generated,
gitignored, rebuilt by the deploy workflow): a leaderboard index at
``/results/`` and, for every run a row or recipe cell links to, that run's
full detail report at ``/results/<run-id>/<anchor>/``. Also writes the report
stylesheet as a site asset and a small data file the navigation and the
landing page read. The HTML rendering lives here on the website side;
everything up to it is the runs' data (``scripts/snapshot_evals.py``).

Usage
-----
    python3 scripts/build_site_benchmark.py
"""

from __future__ import annotations

import json
import shutil
import sys
from html import escape
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from evals import leaderboard  # noqa: E402
from evals.dataset.recipes import RECIPES, headline_categories  # noqa: E402
from evals.render import render_html  # noqa: E402

SITE = REPO / "site"
BENCHMARK = REPO / "benchmark"
OUT = SITE / "results"


def _load_models() -> list[dict[str, Any]]:
    """Return every tracked run's report model, newest-unaffected order."""
    models = []
    for bundle in sorted(BENCHMARK.glob("*/model.json")):
        try:
            models.append(json.loads(bundle.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return models


def _hero_entries() -> list[dict[str, Any]]:
    """Return the curated hero questions (``site/_data/hero_questions.json``)."""
    path = SITE / "_data" / "hero_questions.json"
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return entries


def _page(layout: str, title: str, permalink: str, body: str, extra: str = "") -> str:
    return (
        "---\n"
        f"layout: {layout}\n"
        f'title: "{title}"\n'
        f"permalink: {permalink}\n"
        f"{extra}"
        "---\n"
        f"{body}\n"
    )


def _pct(value: float) -> int:
    return round(value * 100)


def _capability(panel: dict[str, Any] | None) -> dict[str, Any] | None:
    if not panel:
        return None
    return {
        "items": panel["items"],
        "questions": panel["questions"],
        "accuracy_pct": _pct(panel["accuracy"]),
        "accuracy_ci_pct": [_pct(bound) for bound in panel["accuracy_ci"]],
    }


def _complete(model: dict[str, Any]) -> bool:
    """Whether a run scored every headline recipe itself (no per-recipe assembly)."""
    categories = model["summary"].get("categories")
    return categories is None or headline_categories() <= set(categories)


def _headline_capable(model: dict[str, Any]) -> bool:
    """Whether a run carries the kind blocks the headline is computed from."""
    summary = model["summary"]
    return all(
        summary.get(kind) is not None for kind in ("overall", "choice", "noul", "score")
    )


def _headline_model(models: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the run the landing page quotes: the newest complete one.

    A partial re-run (one recipe) refreshes its leaderboard column but cannot
    stand in for the whole headline, so the landing page skips it; a run
    without the kind blocks cannot produce a headline at all. When no run is
    complete, the newest capable run stands in; when none is capable, ``None``
    means the landing ships without a headline.
    """
    capable = [m for m in models if _headline_capable(m)]
    complete = [m for m in capable if _complete(m)]
    pool = complete or capable
    if not pool:
        return None
    return max(pool, key=lambda m: str(m["meta"].get("run_at", "")))


def headline(model: dict[str, Any]) -> dict[str, Any]:
    """Pick the numbers the landing page shows, rounded for display.

    The headline is the coding scope (``scope``): the five agent-kit recipes.
    Vision runs are reported separately as the ``capability`` panel.
    """
    summary = model["summary"]
    confident = [summary[kind]["acting"] for kind in ("choice", "noul")]
    answered = sum(acting["n"] for acting in confident)
    asked = summary["choice"]["n"] + summary["noul"]["n"]
    bands = summary["choice"]["reliability"]
    return {
        "items": summary["overall"]["items"],
        "questions": summary["overall"]["questions"],
        "accuracy_pct": _pct(summary["overall"]["accuracy"]),
        "accuracy_ci_pct": [_pct(bound) for bound in summary["overall"]["accuracy_ci"]],
        "confident": {
            "answered": answered,
            "asked": asked,
            "correct": round(sum(a["n"] * a["accuracy"] for a in confident)),
            "share_pct": _pct(answered / asked),
        },
        "score": {
            "exact_pct": _pct(summary["score"]["accuracy"]),
            "within_one_pct": _pct(summary["score"]["within_one"]),
        },
        "reliability": [
            {
                "claimed_pct": _pct(band["confidence"]),
                "actual_pct": _pct(band["accuracy"]),
                "n": band["n"],
            }
            for band in bands
        ],
        "conservative": all(band["accuracy"] >= band["confidence"] for band in bands),
        "latency": {
            "p50_s": f"{model['latency']['p50'] / 1000:.2f}",
            "p95_s": f"{model['latency']['p95'] / 1000:.2f}",
        },
        "host": model["meta"]["host"]["cpu"],
        "scope": "coding",
        "capability": _capability(summary.get("capability")),
    }


def hero_questions(
    model: dict[str, Any], entries: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Fill the landing page's hero questions with the run's own answers.

    Each curated entry names a benchmark item, one of its questions, and the
    answer its wording assumes (``expect``). An entry is kept only when the
    run answered that question correctly and with that answer, so the hero
    never shows a number the model did not produce. ``{p}`` in ``detail``
    becomes the model's confidence in its answer, as a whole percentage.
    """
    items = {item["id"]: item for item in model["items"]}
    shown = []
    for entry in entries:
        item = items.get(entry["id"])
        answer = item["questions"].get(entry["question"]) if item else None
        if (
            not answer
            or not answer["correct"]
            or answer["predicted"] != entry["expect"]
        ):
            continue
        shown.append(
            {
                "ask": entry["ask"],
                "verdict": entry["verdict"],
                "detail": entry["detail"].replace(
                    "{p}", str(_pct(answer["confidence"]))
                ),
            }
        )
    return shown


def _version_cell(row: dict[str, Any]) -> str:
    server_v = row["ember_server_version"]
    client_v = row["ember_client_version"]
    if server_v and client_v and server_v != client_v:
        return f"server {escape(server_v)}, client {escape(client_v)}"
    version = server_v or client_v
    return escape(version) if version else "not recorded"


def _run_url(run_id: str) -> str:
    return f"{{{{ '/results/{run_id}/summary/' | relative_url }}}}"


def _headline_cell(row: dict[str, Any]) -> str:
    recipes = row.get("recipes") or {}
    if row.get("incomplete") or row.get("accuracy") is None:
        missing = ", ".join(sorted(headline_categories() - set(recipes)))
        return f'<td title="not yet scored: {escape(missing)}">—</td>'
    text = f"{_pct(row['accuracy'])}%"
    if row.get("accuracy_ci"):
        lo, hi = row["accuracy_ci"]
        text += f" [{_pct(lo)}, {_pct(hi)}]"
    return f"<td>{text}</td>"


def _recipe_cell(row: dict[str, Any], category: str) -> str:
    column = (row.get("recipes") or {}).get(category)
    if not column:
        return "<td>—</td>"
    link = f'<a href="{_run_url(column["run_id"])}">{_pct(column["accuracy"])}%</a>'
    return f"<td>{link}</td>"


def _risk_cell(row: dict[str, Any]) -> str:
    blocks = [
        block
        for block in (row.get("risk") or {}).values()
        if block.get("dangerous_recall_at_threshold") is not None
    ]
    if not blocks:
        return "<td>—</td>"
    worst = min(blocks, key=lambda block: block["dangerous_recall_at_threshold"])
    text = f"{_pct(worst['dangerous_recall_at_threshold'])}%"
    if any(block.get("met") is False for block in blocks):
        text += " (not met)"
    missed = sum(int(block.get("missed_dangers") or 0) for block in blocks)
    return f'<td title="{missed} dangerous options missed">{text}</td>'


def _probe_cell(row: dict[str, Any]) -> str:
    """The long-context shape: cap / first-drop / worst depth, or not measured."""
    probe = row.get("probe")
    if not probe:
        return "<td>not measured</td>"
    cap = probe.get("request_cap")
    drop = probe.get("first_drop_length")
    depth = probe.get("worst_depth")
    cap_text = f"{cap:,}" if cap else "—"
    drop_text = f"{drop:,}" if drop else "—"
    depth_text = escape(str(depth)) if depth else "—"
    return f"<td>cap {cap_text} · drop {drop_text} · {depth_text}</td>"


def _tiers_cell(row: dict[str, Any]) -> str:
    """Non-easy accuracy, so a strong headline cannot hide the hard slice."""
    tiers = row.get("tiers")
    if not tiers or tiers.get("non_easy_accuracy") is None:
        return "<td>—</td>"
    return f"<td>{_pct(tiers['non_easy_accuracy'])}%</td>"


def _leaderboard_table_html(rows: list[dict[str, Any]]) -> str:
    categories = [
        c for c in RECIPES if any(c in (r.get("recipes") or {}) for r in rows)
    ]
    recipe_headers = "".join(f"<th>{escape(RECIPES[c].title)}</th>" for c in categories)
    header = (
        "<tr><th>Model</th><th>Deployment</th><th>Device</th>"
        f"<th>Headline</th><th>Items correct</th><th>Non-easy</th>{recipe_headers}"
        "<th>Capability</th><th>Dangerous recall</th><th>Long context</th>"
        "<th>Latency p50</th>"
        "<th>ember version</th><th>Run at</th></tr>"
    )
    body_rows = []
    for row in rows:
        model_label = row["model_repo"] or row["model_name"]
        params = f" ({escape(row['params'])})" if row.get("params") else ""
        item_accuracy = (
            f"{_pct(row['item_accuracy'])}%"
            if row.get("item_accuracy") is not None
            else "—"
        )
        capability = row.get("capability")
        capability_text = (
            f"{_pct(capability['accuracy'])}% ({capability['questions']} q)"
            if capability
            else "—"
        )
        latency = (
            f"{row['latency_p50']:.0f} ms" if row["latency_p50"] is not None else "—"
        )
        body_rows.append(
            "<tr>"
            f'<td><a href="{_run_url(row["run_id"])}">'
            f"{escape(str(model_label))}{params}</a></td>"
            f"<td>{escape(row['deployment_label'] or '?')}</td>"
            f"<td>{escape(row['device'] or '?')}</td>"
            f"{_headline_cell(row)}"
            f"<td>{item_accuracy}</td>"
            f"{_tiers_cell(row)}"
            f"{''.join(_recipe_cell(row, c) for c in categories)}"
            f"<td>{capability_text}</td>"
            f"{_risk_cell(row)}"
            f"{_probe_cell(row)}"
            f"<td>{latency}</td>"
            f"<td>{_version_cell(row)}</td>"
            f"<td>{escape(row['run_at'])}</td>"
            "</tr>"
        )
    return (
        '<table class="leaderboard">'
        f"<thead>{header}</thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _version_heading(version: dict[str, Any]) -> str:
    items = max((row.get("items") or 0 for row in version["rows"]), default=0)
    count = f" · {items} coding items" if items else ""
    badge = " <small>(current)</small>" if version.get("newest") else ""
    digest = escape(str(version["dataset_content_sha256"])[:12])
    return f"<h2>Dataset <code>{digest}</code>{count}{badge}</h2>"


def _leaderboard_page_body(board: dict[str, Any]) -> str:
    versions = board.get("versions") or []
    if not any(version["rows"] for version in versions):
        return "<p>No benchmark runs are tracked yet.</p>"
    intro = (
        "<p>One table per dataset version, newest first; results on different "
        "versions are not compared. One row per model, deployment, and engine "
        "settings. The headline covers the five coding recipes and appears once "
        "every one has been scored; each recipe cell links to the run that "
        "produced it, and a dash marks a recipe not yet scored on this version. "
        "Vision is reported separately as capability.</p>"
    )
    tables = "".join(
        _version_heading(version) + _leaderboard_table_html(version["rows"])
        for version in versions
        if version["rows"]
    )
    return intro + tables


def _write_run_pages(model: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    """Write one run's full detail report under ``/results/<run_id>/``."""
    run_out = OUT / run_id
    run_out.mkdir(parents=True, exist_ok=True)
    sections = render_html.section_html(model)
    for anchor, number, section_title, html in sections:
        (run_out / f"{anchor}.md").write_text(
            _page(
                "benchmark",
                section_title,
                f"/results/{run_id}/{anchor}/",
                html,
                extra=f"section_number: {number}\nrun_id: {run_id}\n",
            ),
            encoding="utf-8",
        )
    return [{"anchor": a, "number": n, "title": t} for a, n, t, _ in sections]


def build() -> int:
    models = _load_models()
    if not models:
        print(
            "error: no benchmark/*/model.json; run scripts/snapshot_evals.py",
            file=sys.stderr,
        )
        return 1

    board = leaderboard.build(models)
    rows = board["rows"]
    models_by_run_id = {m["meta"]["run_id"]: m for m in models}
    linked: list[str] = []
    for version in board["versions"]:
        for row in version["rows"]:
            for run_id in (
                row["run_id"],
                *(c["run_id"] for c in row["recipes"].values()),
            ):
                if run_id not in linked and run_id in models_by_run_id:
                    linked.append(run_id)

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    (SITE / "assets").mkdir(exist_ok=True)
    # The report hero gradient is provided site-wide by the page background
    # (`body` in site.css), so drop it here to avoid a second, narrower band.
    hero_override = "\n.hero { background: none; border-bottom: 0; }\n"
    (SITE / "assets" / "benchmark.css").write_text(
        render_html.css() + hero_override, encoding="utf-8"
    )

    runs: dict[str, Any] = {}
    for run_id in linked:
        model = models_by_run_id[run_id]
        sections = _write_run_pages(model, run_id)
        runs[run_id] = {
            "title": model["text"]["title"],
            "run_at": model["meta"]["run_at"],
            "sections": sections,
        }

    (OUT / "index.md").write_text(
        _page("leaderboard", "Leaderboard", "/results/", _leaderboard_page_body(board)),
        encoding="utf-8",
    )

    # The landing page shows the newest complete run, not the most accurate
    # one: a rerun on a grown benchmark must replace the old figures, never
    # hide behind a smaller, easier run.
    newest = _headline_model(models)
    (SITE / "_data" / "benchmark.json").write_text(
        json.dumps(
            {
                "leaderboard": {"versions": board["versions"], "rows": rows},
                "runs": runs,
                "headline": headline(newest) if newest else None,
                "hero": hero_questions(newest, _hero_entries()) if newest else [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"benchmark site: {len(board['versions'])} dataset versions, "
        f"{sum(len(v['rows']) for v in board['versions'])} leaderboard rows, "
        f"{sum(len(r['sections']) for r in runs.values())} total sections "
        "-> site/results/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
