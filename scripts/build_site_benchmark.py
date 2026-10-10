#!/usr/bin/env python3
"""Render every tracked benchmark bundle into the Jekyll site.

Reads every ``benchmark/<run-id>/model.json``, groups them into a leaderboard
(``evals.leaderboard.build``: one row per distinct model and deployment, the
latest run when a pair has been re-run), and writes native site pages under
``site/results/`` (generated, gitignored, rebuilt by the deploy workflow): a
leaderboard index at ``/results/`` and, for every leaderboard row, the row's
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


def headline(model: dict[str, Any]) -> dict[str, Any]:
    """Pick the numbers the landing page shows, rounded for display."""
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
    }


def _version_cell(row: dict[str, Any]) -> str:
    server_v = row["ember_server_version"]
    client_v = row["ember_client_version"]
    if server_v and client_v and server_v != client_v:
        return f"server {escape(server_v)}, client {escape(client_v)}"
    version = server_v or client_v
    return escape(version) if version else "not recorded"


def _leaderboard_table_html(rows: list[dict[str, Any]]) -> str:
    header = (
        "<tr><th>Model</th><th>Deployment</th><th>Device</th>"
        "<th>Accuracy</th><th>Items correct</th><th>Latency p50</th>"
        "<th>ember version</th><th>Run at</th></tr>"
    )
    body_rows = []
    for row in rows:
        model_label = row["model_repo"] or row["model_name"]
        params = f" ({escape(row['params'])})" if row.get("params") else ""
        deployment = escape(row["deployment_label"] or "?")
        device = escape(row["device"] or "?")
        accuracy_lo, accuracy_hi = row["accuracy_ci"]
        accuracy = (
            f"{_pct(row['accuracy'])}% [{_pct(accuracy_lo)}, {_pct(accuracy_hi)}]"
        )
        item_accuracy = f"{_pct(row['item_accuracy'])}%"
        latency = (
            f"{row['latency_p50']:.0f} ms" if row["latency_p50"] is not None else "—"
        )
        run_url = f"/results/{row['run_id']}/summary/"
        body_rows.append(
            "<tr>"
            f'<td><a href="{run_url}">{escape(str(model_label))}{params}</a></td>'
            f"<td>{deployment}</td>"
            f"<td>{device}</td>"
            f"<td>{accuracy}</td>"
            f"<td>{item_accuracy}</td>"
            f"<td>{latency}</td>"
            f"<td>{_version_cell(row)}</td>"
            f"<td>{escape(row['run_at'])}</td>"
            "</tr>"
        )
    return (
        '<table class="leaderboard">'
        f"<thead>{header}</thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _leaderboard_page_body(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No benchmark runs are tracked yet.</p>"
    intro = (
        "<p>One row per model and deployment combination; re-running the same "
        "pair replaces its row with the latest result. Each model links to its "
        "full benchmark report.</p>"
    )
    return intro + _leaderboard_table_html(rows)


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
    for row in rows:
        run_id = row["run_id"]
        model = models_by_run_id[run_id]
        sections = _write_run_pages(model, run_id)
        runs[run_id] = {
            "title": model["text"]["title"],
            "run_at": model["meta"]["run_at"],
            "sections": sections,
        }

    (OUT / "index.md").write_text(
        _page("leaderboard", "Leaderboard", "/results/", _leaderboard_page_body(rows)),
        encoding="utf-8",
    )

    top_model = models_by_run_id[rows[0]["run_id"]] if rows else None
    (SITE / "_data" / "benchmark.json").write_text(
        json.dumps(
            {
                "leaderboard": {"rows": rows},
                "runs": runs,
                "headline": headline(top_model) if top_model is not None else None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"benchmark site: {len(rows)} leaderboard rows, "
        f"{sum(len(r['sections']) for r in runs.values())} total sections "
        "-> site/results/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
