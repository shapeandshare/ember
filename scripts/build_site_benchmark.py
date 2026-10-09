#!/usr/bin/env python3
"""Render the tracked benchmark bundle into the Jekyll site.

Reads the newest ``benchmark/<run-id>/model.json`` and writes native site pages
under ``site/results/`` (generated, gitignored, rebuilt by the deploy workflow),
the report stylesheet as a site asset, and a small data file the navigation
reads. The HTML rendering lives here on the website side; everything up to it is
the run's data (``scripts/snapshot_evals.py``).

Usage
-----
    python3 scripts/build_site_benchmark.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from evals.render import render_html  # noqa: E402

SITE = REPO / "site"
BENCHMARK = REPO / "benchmark"
OUT = SITE / "results"


def _latest_model() -> Path | None:
    bundles = sorted(BENCHMARK.glob("*/model.json"), key=lambda p: p.parent.name)
    return bundles[-1] if bundles else None


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


def build() -> int:
    model_path = _latest_model()
    if model_path is None:
        print(
            "error: no benchmark/*/model.json; run scripts/snapshot_evals.py",
            file=sys.stderr,
        )
        return 1
    model = json.loads(model_path.read_text(encoding="utf-8"))
    run_id = model_path.parent.name
    meta = model["meta"]
    title = model["text"]["title"]

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    (SITE / "assets").mkdir(exist_ok=True)
    # The report hero gradient is provided site-wide by the page background
    # (`body` in site.css), so drop it here to avoid a second, narrower band.
    hero_override = "\n.hero { background: none; border-bottom: 0; }\n"
    (SITE / "assets" / "benchmark.css").write_text(
        render_html.css() + hero_override, encoding="utf-8"
    )

    sections = render_html.section_html(model)

    for anchor, number, section_title, html in sections:
        (OUT / f"{anchor}.md").write_text(
            _page(
                "benchmark",
                section_title,
                f"/results/{anchor}/",
                html,
                extra=f"section_number: {number}\n",
            ),
            encoding="utf-8",
        )

    (SITE / "_data" / "benchmark.json").write_text(
        json.dumps(
            {
                "run": {"id": run_id, "title": title, "run_at": meta["run_at"]},
                "headline": headline(model),
                "sections": [
                    {"anchor": a, "number": n, "title": t} for a, n, t, _ in sections
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"benchmark site: {run_id} · {len(sections)} sections -> site/results/")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
