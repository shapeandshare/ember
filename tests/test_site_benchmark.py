"""The site's benchmark pages: a leaderboard index plus one full detail
report per tracked (model, deployment) run, built from every snapshotted
``benchmark/<run-id>/model.json``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_site_benchmark.py"
REAL_BENCHMARK = ROOT / "benchmark"


def _load_build_site_benchmark() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_site_benchmark", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bench = _load_build_site_benchmark()

MODEL = {
    "meta": {"host": {"cpu": "Apple M4 Max"}},
    "summary": {
        "overall": {
            "items": 264,
            "questions": 456,
            "accuracy": 0.8443,
            "accuracy_ci": [0.8092, 0.8772],
        },
        "choice": {
            "n": 192,
            "acting": {"n": 123, "coverage": 0.6406, "accuracy": 1.0},
            "reliability": [
                {
                    "low": 0.3,
                    "high": 0.4,
                    "n": 4,
                    "confidence": 0.3808,
                    "accuracy": 0.5,
                },
                {
                    "low": 0.9,
                    "high": 1.0,
                    "n": 104,
                    "confidence": 0.949,
                    "accuracy": 1.0,
                },
            ],
        },
        "noul": {"n": 168, "acting": {"n": 111, "coverage": 0.6607, "accuracy": 1.0}},
        "score": {"n": 96, "accuracy": 0.5312, "within_one": 0.8542},
    },
    "latency": {"p50": 922.5, "p95": 1091.1},
}


def _real_bundles() -> list[Path]:
    """Copy of every tracked ``benchmark/<run-id>/`` directory for a sandboxed build."""
    return sorted(REAL_BENCHMARK.glob("*/model.json"))


def _leaderboard_row(**overrides: object) -> dict:
    row = {
        "run_id": "clef-flash_20261010T000000Z",
        "run_at": "2026-10-10 00:00 UTC",
        "model_key": "flash",
        "model_name": "clef-flash",
        "model_repo": "Cloudflare/clef-flash",
        "params": "9B",
        "deployment_key": "Remote hosted (GPU, CUDA)|cuda",
        "deployment_label": "Remote hosted (GPU, CUDA)",
        "device": "cuda",
        "dtype": "float16",
        "ember_server_version": "0.10.2",
        "ember_client_version": "0.10.2",
        "accuracy": 0.827,
        "accuracy_ci": [0.802, 0.853],
        "item_accuracy": 0.743,
        "items": 475,
        "questions": 843,
        "latency_p50": 503.6,
        "latency_p95": 630.1,
    }
    row.update(overrides)
    return row


def test_leaderboard_table_shows_the_deployment_label_not_a_url() -> None:
    html = bench._leaderboard_table_html([_leaderboard_row()])
    assert "Remote hosted (GPU, CUDA)" in html
    assert "://" not in html


def test_leaderboard_table_run_link_uses_relative_url_for_baseurl() -> None:
    """The site is a GitHub Pages project page served under ``/ember/``.

    A raw ``href="/results/.../summary/"`` link bypasses Jekyll's baseurl and
    404s when deployed; the link must go through the ``relative_url`` filter,
    as every other internal link in the generated/templated site does.
    """
    row = _leaderboard_row(run_id="clef-flash_20261010T000000Z")
    html = bench._leaderboard_table_html([row])
    assert (
        "href=\"{{ '/results/clef-flash_20261010T000000Z/summary/' | relative_url }}\">"
    ) in html
    assert 'href="/results/' not in html


def test_leaderboard_table_never_leaks_a_real_hostname() -> None:
    """Even if a row's ``deployment_label`` somehow contained a scheme-less
    hostname fragment, the table must never surface anything resembling a
    URL for any field it renders (model, deployment, version, run_at).
    """
    row = _leaderboard_row(
        deployment_label="Remote hosted (GPU, CUDA)",
    )
    html = bench._leaderboard_table_html([row])
    for forbidden in ("http://", "https://", ".outerbounds.", ".com/"):
        assert forbidden not in html


def test_headline_reports_the_numbers_the_landing_page_shows() -> None:
    assert bench.headline(MODEL) == {
        "items": 264,
        "questions": 456,
        "accuracy_pct": 84,
        "accuracy_ci_pct": [81, 88],
        "confident": {"answered": 234, "asked": 360, "correct": 234, "share_pct": 65},
        "score": {"exact_pct": 53, "within_one_pct": 85},
        "reliability": [
            {"claimed_pct": 38, "actual_pct": 50, "n": 4},
            {"claimed_pct": 95, "actual_pct": 100, "n": 104},
        ],
        "conservative": True,
        "latency": {"p50_s": "0.92", "p95_s": "1.09"},
        "host": "Apple M4 Max",
        "scope": "coding",
        "capability": None,
    }


def test_headline_is_not_conservative_when_a_band_overclaims() -> None:
    bands = MODEL["summary"]["choice"]["reliability"]
    overclaiming = {**bands[0], "confidence": 0.62, "accuracy": 0.5}
    choice = {**MODEL["summary"]["choice"], "reliability": [overclaiming, bands[1]]}
    model = {**MODEL, "summary": {**MODEL["summary"], "choice": choice}}
    assert bench.headline(model)["conservative"] is False


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy every real tracked bundle into a sandbox benchmark/ tree."""
    import shutil

    bundles = REAL_BENCHMARK.glob("*")
    sandbox_benchmark = tmp_path / "benchmark"
    sandbox_benchmark.mkdir()
    for run_dir in bundles:
        if run_dir.is_dir():
            shutil.copytree(run_dir, sandbox_benchmark / run_dir.name)
    sandbox_site = tmp_path / "site"
    (sandbox_site / "_data").mkdir(parents=True)
    (sandbox_site / "assets").mkdir()
    monkeypatch.setattr(bench, "BENCHMARK", sandbox_benchmark)
    monkeypatch.setattr(bench, "SITE", sandbox_site)
    monkeypatch.setattr(bench, "OUT", sandbox_site / "results")
    return sandbox_site


def test_build_writes_one_detail_page_set_per_leaderboard_row(sandbox: Path) -> None:
    assert bench.build() == 0
    data = json.loads(
        (sandbox / "_data" / "benchmark.json").read_text(encoding="utf-8")
    )
    run_ids = {row["run_id"] for row in data["leaderboard"]["rows"]}
    assert len(run_ids) >= 1
    for run_id in run_ids:
        run_dir = sandbox / "results" / run_id
        assert run_dir.is_dir(), f"missing detail pages for {run_id}"
        assert (run_dir / "summary.md").exists()


def test_build_writes_a_leaderboard_index_page(sandbox: Path) -> None:
    assert bench.build() == 0
    index = sandbox / "results" / "index.md"
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "permalink: /results/" in text


def test_leaderboard_index_uses_the_full_width_layout_not_the_sidebar_one(
    sandbox: Path,
) -> None:
    """The leaderboard index has no per-page section nav (only a per-run
    report does, via ``benchmark_nav.html``), so it must use the
    sidebar-free ``leaderboard`` layout rather than ``benchmark`` — the
    latter reserves a 220px nav column that would render empty on this
    page.
    """
    assert bench.build() == 0
    text = (sandbox / "results" / "index.md").read_text(encoding="utf-8")
    assert "layout: leaderboard" in text


def test_build_writes_the_headline_from_the_newest_run(sandbox: Path) -> None:
    assert bench.build() == 0
    data = json.loads(
        (sandbox / "_data" / "benchmark.json").read_text(encoding="utf-8")
    )
    models = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (sandbox.parent / "benchmark").glob("*/model.json")
    ]
    newest = max(models, key=lambda m: m["meta"]["run_at"])
    assert data["headline"] == bench.headline(newest)


def test_build_with_no_tracked_runs_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_benchmark = tmp_path / "benchmark"
    empty_benchmark.mkdir()
    sandbox_site = tmp_path / "site"
    (sandbox_site / "_data").mkdir(parents=True)
    monkeypatch.setattr(bench, "BENCHMARK", empty_benchmark)
    monkeypatch.setattr(bench, "SITE", sandbox_site)
    monkeypatch.setattr(bench, "OUT", sandbox_site / "results")
    assert bench.build() == 1


# Hero questions: a curated pool whose numbers come from the newest run

HERO_ITEM = {
    "id": "risk_020",
    "questions": {
        "needs_review": {
            "type": "noul",
            "predicted": True,
            "correct": True,
            "confidence": 0.9213,
        }
    },
}
HERO_ENTRY = {
    "id": "risk_020",
    "question": "needs_review",
    "expect": True,
    "ask": "Removing auth to cut latency. Push?",
    "verdict": "Stop.",
    "detail": "{p}% needs review.",
}


def test_hero_questions_fill_the_percentage_from_the_run() -> None:
    model = {"items": [HERO_ITEM]}
    assert bench.hero_questions(model, [HERO_ENTRY]) == [
        {
            "ask": "Removing auth to cut latency. Push?",
            "verdict": "Stop.",
            "detail": "92% needs review.",
        }
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"correct": False},
        {"predicted": False},
    ],
)
def test_hero_questions_drop_answers_the_model_did_not_give(
    change: dict[str, object],
) -> None:
    item = {
        **HERO_ITEM,
        "questions": {
            "needs_review": {**HERO_ITEM["questions"]["needs_review"], **change}
        },
    }
    assert bench.hero_questions({"items": [item]}, [HERO_ENTRY]) == []


def test_hero_questions_drop_an_item_missing_from_the_run() -> None:
    assert bench.hero_questions({"items": []}, [HERO_ENTRY]) == []


def test_every_curated_hero_question_holds_in_the_newest_run() -> None:
    models = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in REAL_BENCHMARK.glob("*/model.json")
    ]
    newest = max(models, key=lambda m: m["meta"]["run_at"])
    entries = json.loads(
        (REAL_BENCHMARK.parent / "site" / "_data" / "hero_questions.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(bench.hero_questions(newest, entries)) == len(entries)


def test_every_hero_reply_is_shorter_than_its_question() -> None:
    models = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in REAL_BENCHMARK.glob("*/model.json")
    ]
    newest = max(models, key=lambda m: m["meta"]["run_at"])
    entries = json.loads(
        (REAL_BENCHMARK.parent / "site" / "_data" / "hero_questions.json").read_text(
            encoding="utf-8"
        )
    )
    long_replies = [
        q["ask"]
        for q in bench.hero_questions(newest, entries)
        if len(f"{q['verdict']} {q['detail']}") >= len(q["ask"])
    ]
    assert long_replies == []


def test_build_writes_leaderboard_versions_newest_first(sandbox: Path) -> None:
    assert bench.build() == 0
    data = json.loads(
        (sandbox / "_data" / "benchmark.json").read_text(encoding="utf-8")
    )
    versions = data["leaderboard"]["versions"]
    assert versions[0]["newest"] is True
    assert [v["run_at"] for v in versions] == sorted(
        (v["run_at"] for v in versions), reverse=True
    )


def test_hero_questions_cover_every_recipe_equally() -> None:
    entries = json.loads(
        (REAL_BENCHMARK.parent / "site" / "_data" / "hero_questions.json").read_text(
            encoding="utf-8"
        )
    )
    per_recipe = Counter(entry["id"].rsplit("_", 1)[0] for entry in entries)
    assert len(set(per_recipe.values())) == 1, per_recipe


def test_probe_cell_renders_figures_or_not_measured() -> None:
    """The leaderboard's long-context cell names the figures, or the gap."""
    module = _load_build_site_benchmark()
    assert "not measured" in module._probe_cell({})
    cell = module._probe_cell(
        {
            "probe": {
                "request_cap": 24576,
                "first_drop_length": 32768,
                "worst_depth": "end",
            }
        }
    )
    assert "24,576" in cell
    assert "32,768" in cell
    assert "end" in cell


def test_tiers_cell_renders_non_easy_accuracy_or_dash() -> None:
    """The leaderboard names the hard slice beside the headline."""
    module = _load_build_site_benchmark()
    assert "—" in module._tiers_cell({})
    cell = module._tiers_cell({"tiers": {"non_easy_accuracy": 0.3967}})
    assert "40%" in cell
