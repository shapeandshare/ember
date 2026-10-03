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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from evals import render_html  # noqa: E402

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
    # The report hero gradient is provided site-wide by `.page-body` (site.css),
    # so drop it here to avoid a second, narrower band under the nav.
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
