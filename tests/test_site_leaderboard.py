"""Site leaderboard, specs/004 Phase 0: the headline's scope and capability
panel, one table per dataset version, incomplete rows, and recipe cells that
link to the run that produced them.

Shares the loaded build script, ``MODEL``, the row factory, and the
``sandbox`` fixture with ``tests/test_site_benchmark.py``.
"""

from __future__ import annotations

from tests.test_site_benchmark import MODEL, _leaderboard_row, bench


def _recipe(run_id: str, accuracy: float = 0.9) -> dict:
    return {
        "accuracy": accuracy,
        "item_accuracy": accuracy,
        "items": 10,
        "recipe_sha256": "r" * 64,
        "run_id": run_id,
        "run_at": "2026-10-10 00:00 UTC",
    }


def _version(content: str, run_at: str, rows: list[dict], *, newest: bool) -> dict:
    return {
        "dataset_content_sha256": content,
        "newest": newest,
        "run_at": run_at,
        "rows": rows,
    }


def test_headline_rounds_the_capability_panel_when_a_run_has_one() -> None:
    capability = {
        "items": 32,
        "questions": 32,
        "accuracy": 1.0,
        "accuracy_ci": [0.89, 1.0],
    }
    model = {**MODEL, "summary": {**MODEL["summary"], "capability": capability}}
    assert bench.headline(model)["capability"] == {
        "items": 32,
        "questions": 32,
        "accuracy_pct": 100,
        "accuracy_ci_pct": [89, 100],
    }


def test_leaderboard_page_renders_one_table_per_version_newest_first() -> None:
    newest = _version(
        "a" * 64, "2026-10-10 00:00 UTC", [_leaderboard_row(run_id="new")], newest=True
    )
    older = _version(
        "b" * 64, "2026-10-01 00:00 UTC", [_leaderboard_row(run_id="old")], newest=False
    )
    html = bench._leaderboard_page_body({"versions": [newest, older]})
    assert html.count("<table") == 2
    assert html.index("a" * 12) < html.index("b" * 12)
    assert html.index("/results/new/summary/") < html.index("/results/old/summary/")


def test_incomplete_rows_show_a_dash_that_names_the_missing_recipes() -> None:
    row = _leaderboard_row(
        accuracy=None,
        accuracy_ci=None,
        item_accuracy=None,
        headline=None,
        incomplete=True,
        recipes={"routing": _recipe("partial")},
    )
    html = bench._leaderboard_table_html([row])
    assert "—" in html
    assert 'title="' in html
    assert "change_risk" in html
    assert "/results/partial/summary/" in html


def test_recipe_cells_link_to_the_run_that_produced_them() -> None:
    row = _leaderboard_row(
        run_id="newest",
        recipes={"routing": _recipe("partial"), "change_risk": _recipe("newest")},
    )
    html = bench._leaderboard_table_html([row])
    assert "{{ '/results/partial/summary/' | relative_url }}" in html
    assert "{{ '/results/newest/summary/' | relative_url }}" in html


def test_headline_model_skips_a_newer_partial_run() -> None:
    complete = {**MODEL, "meta": {**MODEL["meta"], "run_id": "complete"}}
    partial = {
        **MODEL,
        "meta": {
            **MODEL["meta"],
            "run_id": "partial",
            "run_at": "2026-12-01 00:00 UTC",
        },
        "summary": {**MODEL["summary"], "categories": {"routing": {}}},
    }
    assert bench._headline_model([complete, partial])["meta"]["run_id"] == "complete"


def test_dangerous_recall_cell_says_plainly_when_the_bar_is_not_met() -> None:
    row = _leaderboard_row(
        risk={
            "routing": {
                "dangerous_recall_at_threshold": 0.9,
                "missed_dangers": 2,
                "bar": 0.95,
                "met": False,
            }
        }
    )
    html = bench._leaderboard_table_html([row])
    assert "90%" in html
    assert "not met" in html
    met = _leaderboard_row(
        risk={
            "routing": {
                "dangerous_recall_at_threshold": 0.97,
                "missed_dangers": 0,
                "bar": 0.95,
                "met": True,
            }
        }
    )
    assert "not met" not in bench._leaderboard_table_html([met])


def test_version_heading_counts_coding_items() -> None:
    version = _version(
        "a" * 64, "2026-10-10 00:00 UTC", [_leaderboard_row(items=443)], newest=True
    )
    assert "443 coding items" in bench._leaderboard_page_body({"versions": [version]})
