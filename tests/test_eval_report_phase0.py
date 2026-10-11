"""Benchmark report additions from specs/004 Phase 0: legends, direction rules,
the capability panel, risk tables, consistency and by-source rows, tiers, and
the token-length figure. Shares the synthetic-run fixtures in ``tests/conftest.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

LEGENDS = (
    "0 Negligible → 3 High",
    "0 Trivial (minutes) → 3 Large (a day or more)",
    "0 No alert (calm green) → 3 High (red)",
)


def test_score_legends_render_in_html_and_markdown(bundle: Path) -> None:
    html = (bundle / "report.html").read_text(encoding="utf-8")
    markdown = (bundle / "report.md").read_text(encoding="utf-8")
    for legend in LEGENDS:
        assert legend in html, legend
        assert legend in markdown, legend


def test_protocol_states_direction_rules(report: dict) -> None:
    protocol = report["text"]["protocol"]
    assert any(
        p.startswith("Every `score` scale runs from least to most") for p in protocol
    )
    assert any(
        p.startswith("For a `noul` question, P(true) is the probability")
        for p in protocol
    )
    assert any("content hash" in p for p in protocol)
    assert not any("Every change alters the dataset's SHA-256" in p for p in protocol)


def test_report_text_lists_every_scale(report: dict) -> None:
    scales = {s["question"]: s for s in report["text"]["scales"]}
    assert set(scales) == {"risk", "effort", "alert_level"}
    assert scales["risk"]["legend"] == "0 Negligible → 3 High"
    assert scales["risk"]["dangerous_end"] == "high"
    assert scales["effort"]["dangerous_end"] == "none"


def test_recipe_score_questions_carry_their_legend(report: dict) -> None:
    for recipe in report["recipes"]:
        for question in recipe["questions"]:
            if question["type"] == "score":
                assert question["legend"] in LEGENDS, (
                    recipe["category"],
                    question["id"],
                )


# ###########################################################################
# Capability panel, risk, consistency, by-source, tiers, tokens
# ###########################################################################


def _write_run(
    directory: Path, run_id: str, scored: list[dict], extra_config: dict
) -> Path:  # type: ignore[type-arg]
    import hashlib
    import json

    from evals import metrics

    from tests.test_eval_benchmark import DATASET

    trace = directory / f"{run_id}_trace.jsonl"
    trace.write_text("".join(json.dumps(r) + "\n" for r in scored), encoding="utf-8")
    config = {
        "run_id": run_id,
        "timestamp": "20261003T000000Z",
        "git_hash": "abc1234",
        "model": "clef-flash",
        "model_spec": {
            "name": "flash",
            "repo": "Cloudflare/clef-flash",
            "params": "9B",
        },
        "engine": {"device": "mps", "dtype": "float16", "max_length": 262144},
        "host": {
            "platform": "macOS",
            "cpu": "Apple M4 Max",
            "python": "3.12",
            "packages": {},
        },
        "dataset": DATASET.name,
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "trace": trace.name,
        "split": None,
        "category": None,
        "n_items": len(scored),
        "n_errors": 0,
        "latency_ms": {"mean": 900.0, "p50": 900.0, "p95": 900.0, "max": 900.0},
        **extra_config,
    }
    results = directory / f"{run_id}_results.json"
    results.write_text(
        json.dumps({"config": config, "summary": metrics.aggregate(scored)}),
        encoding="utf-8",
    )
    return results


def test_summary_states_the_headline_scope(report: dict) -> None:
    assert report["summary"]["capability"] is not None
    assert "capability panel" in report["text"]["headline_scope"]


def test_results_render_the_capability_panel(bundle: Path) -> None:
    html = (bundle / "report.html").read_text(encoding="utf-8")
    markdown = (bundle / "report.md").read_text(encoding="utf-8")
    for text in (html, markdown):
        assert "Capability panel" in text
        assert "vision_noul" in text
        assert (
            "Headline over coding recipes; vision recipes in the capability panel"
            in text
        )


def test_meta_carries_the_phase_0_hashes_and_token_availability(report: dict) -> None:
    meta = report["meta"]
    for key in (
        "dataset_content_sha256",
        "recipe_sha256",
        "register_sha256",
        "settings",
    ):
        assert key in meta, key
    assert meta["tokens_available"] is False
    assert "content_sha256" in meta["dataset"]


def test_risk_consistency_by_source_and_tiers_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from evals import analysis, export, metrics
    from evals.dataset import recipes
    from evals.dataset.records.family import Family

    from tests.test_eval_benchmark import DATASET, ITEMS, _answers

    risky = recipes.RECIPES["routing"].model_copy(
        update={
            "risk": True,
            "family": Family.risk_trio,
            "dangerous_options": {"owner": frozenset({"unclear"})},
        }
    )
    monkeypatch.setitem(recipes.RECIPES, "routing", risky)
    routing = [item for item in ITEMS if item["category"] == "routing"][:12]
    scored = []
    for index, item in enumerate(routing):
        result = metrics.score_item(item, _answers(item, right=index % 4 != 0))
        result.update(
            latency_ms=900.0,
            model="clef-flash",
            usage={},
            answers={},
            tokens={
                "total": 200 + index,
                "state": 30 + index,
                "fixed": 170,
                "media": 0,
            },
            kind=None,
            tier="easy" if index % 3 == 0 else None,
            source_kind="imported" if index % 2 else "authored",
            parent_id=routing[0]["id"] if index in (1, 2) else None,
            perturbation="paraphrase" if index in (1, 2) else None,
        )
        scored.append(result)
    results = _write_run(tmp_path, "clef-flash_20261010T000000Z", scored, {})
    model = analysis.build(results, dataset_path=DATASET)
    assert set(model["summary"]["risk"]) == {"routing"}
    assert model["summary"]["consistency"]["routing"]["groups"] == 1
    assert set(model["summary"]["by_source_kind"]["routing"]) == {
        "authored",
        "imported",
    }
    assert model["summary"]["tiers"]["easy_items"] == 4
    assert model["meta"]["tokens_available"] is True
    bundle = export.export(results, tmp_path / "bundle")
    html = (bundle / "report.html").read_text(encoding="utf-8")
    markdown = (bundle / "report.md").read_text(encoding="utf-8")
    for text in (html, markdown):
        assert "Dangerous recall" in text
        assert "Consistency" in text
        assert "By source" in text
        assert "Non-easy" in text
    assert (bundle / "figures" / "tokens.svg").is_file()
    assert "<svg" in (bundle / "figures" / "tokens.svg").read_text(encoding="utf-8")


def test_pre_phase_0_traces_report_the_split_as_unavailable(bundle: Path) -> None:
    markdown = (bundle / "report.md").read_text(encoding="utf-8")
    assert "token split is unavailable" in markdown
    assert not (bundle / "figures" / "tokens.svg").exists()


def test_limitations_name_a_single_rater_not_an_annotation_team(bundle: Path) -> None:
    for name in ("report.html", "report.md"):
        text = (bundle / name).read_text(encoding="utf-8")
        assert "Single rater" in text
        assert "One annotation team" not in text
        assert "label stability" in text
        assert "inter-annotator agreement yet" not in text


def test_empty_non_easy_subset_is_stated_not_tabulated(tmp_path: Path) -> None:
    from evals import analysis, export, metrics

    from tests.test_eval_benchmark import DATASET, ITEMS, _answers

    routing = [item for item in ITEMS if item["category"] == "routing"][:6]
    scored = []
    for item in routing:
        result = metrics.score_item(item, _answers(item, right=True))
        result.update(
            latency_ms=900.0, model="clef-flash", usage={}, answers={}, tier="easy"
        )
        scored.append(result)
    results = _write_run(tmp_path, "clef-flash_20261010T000001Z", scored, {})
    model = analysis.build(results, dataset_path=DATASET)
    assert model["summary"]["tiers"]["non_easy"]["items"] == 0
    bundle = export.export(results, tmp_path / "bundle")
    for name in ("report.html", "report.md"):
        text = (bundle / name).read_text(encoding="utf-8")
        assert "non-easy subset is empty" in text
        assert "Non-easy" not in text


def test_report_states_the_policy_text_in_force(
    report: dict, bundle: Path, tmp_path: Path
) -> None:
    from evals import analysis, export, metrics

    from tests.test_eval_benchmark import DATASET, ITEMS, _answers

    assert report["meta"]["policy"] == {}
    for name in ("report.html", "report.md"):
        text = (bundle / name).read_text(encoding="utf-8")
        assert "Policy in force" in text
        assert "default criteria" in text
    routing = [item for item in ITEMS if item["category"] == "routing"][:3]
    scored = []
    for item in routing:
        result = metrics.score_item(item, _answers(item, right=True))
        result.update(latency_ms=900.0, model="clef-flash", usage={}, answers={})
        scored.append(result)
    policy = {"routing": "Escalate anything touching billing to the payments owner."}
    results = _write_run(
        tmp_path, "clef-flash_20261010T000002Z", scored, {"policy": policy}
    )
    model = analysis.build(results, dataset_path=DATASET)
    assert model["meta"]["policy"] == policy
    out = export.export(results, tmp_path / "bundle")
    assert "payments owner" in (out / "report.md").read_text(encoding="utf-8")


def test_design_renders_the_generated_dataset_card(report: dict, bundle: Path) -> None:
    card = report["card"]
    assert len(card["dataset_content_sha256"]) == 64
    recorded = report["meta"]["dataset_content_sha256"]
    assert recorded is None or recorded == card["dataset_content_sha256"]
    routing = card["recipes"]["routing"]
    assert routing["items"] == routing["dev"] + routing["test"]
    assert routing["rater_count"] == 1
    assert "owner" in routing["per_label_per_split"]
    for name in ("report.html", "report.md"):
        text = (bundle / name).read_text(encoding="utf-8")
        assert "Generated card" in text
        assert "Second review" in text
        assert "Rater" in text
        # one row per recipe in the run
        for category in report["summary"]["categories"]:
            assert f"`{category}`" in text or f"<code>{category}</code>" in text


def test_protocol_bullets_name_the_version_each_rule_applies_from(
    report: dict, bundle: Path
) -> None:
    from evals.dataset import protocol

    protocol_text = report["text"]["protocol"]
    assert len(protocol_text) == len(protocol.RULES)
    for bullet, rule in zip(protocol_text, protocol.RULES, strict=True):
        assert rule.since[:12] in bullet
    assert "since dataset version" in (bundle / "report.md").read_text(encoding="utf-8")


def test_headline_scope_states_the_composition_change(report: dict) -> None:
    scope = report["text"]["headline_scope"]
    assert "counted toward the headline before" in scope
