"""Benchmark report: the report model built from a run, and its rendered exports.

A synthetic run (scripted answers, every third item wrong) stands in for the
model, so nothing here loads it.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from evals import analysis, metrics

from tests.test_eval_benchmark import DATASET, ITEMS, _answers


@pytest.fixture(scope="module")
def synthetic_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write a results file and trace the way ``scripts/run_evals.py`` does."""
    directory = tmp_path_factory.mktemp("results")
    run_id = "clef-flash_20261003T000000Z"
    scored = []
    for index, item in enumerate(ITEMS):
        result = metrics.score_item(item, _answers(item, right=index % 3 != 0))
        result.update(
            latency_ms=900.0 + index, model="clef-flash", usage={}, answers={}
        )
        scored.append(result)
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
            "revision": "17f0b0a",
        },
        "engine": {"device": "mps", "dtype": "float16", "max_length": 262144},
        "host": {
            "platform": "macOS-26.0-arm64",
            "cpu": "Apple M4 Max",
            "python": "3.12.11",
            "packages": {"torch": "2.14.1"},
        },
        "server": "http://127.0.0.1:8765",
        "dataset": DATASET.name,
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "trace": trace.name,
        "split": None,
        "category": None,
        "n_items": len(scored),
        "n_errors": 0,
        "latency_ms": {"mean": 957.5, "p50": 957.0, "p95": 1009.0, "max": 1015.0},
    }
    results = directory / f"{run_id}_results.json"
    results.write_text(
        json.dumps({"config": config, "summary": metrics.aggregate(scored)}),
        encoding="utf-8",
    )
    return results


@pytest.fixture(scope="module")
def report(synthetic_run: Path) -> dict:
    return analysis.build(synthetic_run, dataset_path=DATASET)


def test_report_model_is_complete_and_serialisable(report: dict) -> None:
    for section in (
        "meta",
        "text",
        "summary",
        "findings",
        "composition",
        "recipes",
        "bands",
        "policies",
        "coverage",
        "confusion",
        "score_spread",
        "splits",
        "latency",
        "items",
        "misses",
    ):
        assert report[section], section
    assert report["meta"]["dataset"]["matches"] is True
    assert len(report["items"]) == len(ITEMS)
    assert {f["tone"] for f in report["findings"]} <= {"good", "warn", "info"}
    json.dumps(report)


def test_narrative_placeholders_are_filled(report: dict) -> None:
    text = report["text"]
    paragraphs = (
        text["dataset"] + text["limitations"] + [a for _, a in text["datasheet"]]
    )
    assert not [p for p in paragraphs if "{" in p or "}" in p]


def test_every_citation_resolves(report: dict) -> None:
    keys = {ref["key"] for ref in report["text"]["references"]}
    blob = json.dumps(report["text"])
    cited = {part.split("]")[0] for part in blob.split("[@")[1:]}
    assert cited <= keys
    assert keys <= cited, f"uncited references: {keys - cited}"


def test_confusion_matrices_add_up(report: dict) -> None:
    for qid, entry in report["confusion"].items():
        answered = [
            i["questions"][qid] for i in report["items"] if qid in i["questions"]
        ]
        matrix = entry["matrix"]
        assert sum(map(sum, matrix)) == len(answered), qid
        diagonal = sum(matrix[k][k] for k in range(len(matrix)))
        assert diagonal == sum(q["correct"] for q in answered), qid


def test_bands_and_policies_partition_their_items(report: dict) -> None:
    for qtype, rows in report["bands"].items():
        assert sum(row["n"] for row in rows) == report["summary"][qtype]["n"], qtype
    for policy in report["policies"]:
        assert (
            policy["right"] + policy["extra_step"] + policy["wrong_action"]
            == policy["n"]
        )
        assert len(policy["cases"]) == policy["extra_step"] + policy["wrong_action"]


def test_coverage_curves_start_full_and_never_grow(report: dict) -> None:
    for qtype, curve in report["coverage"].items():
        coverage = [p["coverage"] for p in curve["points"]]
        assert coverage[0] == 1.0, qtype
        assert coverage == sorted(coverage, reverse=True), qtype


def test_misses_carry_the_evidence_a_reviewer_needs(report: dict) -> None:
    assert len(report["misses"]) == len(report["summary"]["misses"])
    for miss in report["misses"]:
        assert miss["state"] is not None, miss["id"]
        assert miss["rationale"], miss["id"]
        assert miss["kit_outcome"], miss["id"]


# ###########################################################################
# Rendered exports
# ###########################################################################

SECTION_IDS = (
    "summary",
    "context",
    "system",
    "design",
    "metrics",
    "results",
    "calibration",
    "decisions",
    "ordinal",
    "confusion",
    "errors",
    "latency",
    "limitations",
    "reproducibility",
    "glossary",
    "references",
    "appendix",
)


@pytest.fixture(scope="module")
def bundle(synthetic_run: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    # import-placement:allow - deferred; loaded only for model-backed tests
    from evals import export

    return export.export(synthetic_run, tmp_path_factory.mktemp("bundle"))


def test_export_writes_the_full_bundle(bundle: Path) -> None:
    for name in (
        "report.html",
        "report.md",
        "data/results.json",
        "data/trace.jsonl",
        "data/dataset.jsonl",
        "figures/ember-light.svg",
    ):
        assert (bundle / name).is_file(), name


def test_html_is_well_formed_self_contained_and_complete(bundle: Path) -> None:
    # import-placement:allow - deferred per test function to avoid eager std-lib load
    from html.parser import HTMLParser

    html = (bundle / "report.html").read_text(encoding="utf-8")
    ids: list[str] = []

    class Collect(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list) -> None:
            ids.extend(value for key, value in attrs if key == "id")

    Collect().feed(html)
    assert set(SECTION_IDS) <= set(ids)
    assert len(ids) == len(set(ids)), "duplicate ids"
    for needle in ("<script src", "<link ", 'src="http', "url(http", "@import"):
        assert needle not in html, needle
    assert "[@" not in html


def test_markdown_references_only_existing_figures(bundle: Path) -> None:
    # import-placement:allow - deferred per test function
    import re

    markdown = (bundle / "report.md").read_text(encoding="utf-8")
    for section in SECTION_IDS:
        assert f'<a id="{section}"></a>' in markdown, section
    referenced = set(re.findall(r'(?:src|srcset)="(figures/[^"]+)"', markdown))
    assert referenced
    assert all((bundle / ref).is_file() for ref in referenced)
    assert "[@" not in markdown


def test_every_figure_is_valid_svg(bundle: Path) -> None:
    # import-placement:allow - deferred per test function
    import xml.etree.ElementTree as ET

    figures = list((bundle / "figures").glob("*.svg"))
    assert len(figures) > 20
    for figure in figures:
        root = ET.fromstring(figure.read_text(encoding="utf-8"))  # noqa: S314 - our own output
        assert root.get("viewBox"), figure.name
        assert root.get("width") is None, figure.name


def test_untrusted_dataset_text_is_escaped(report: dict) -> None:
    # import-placement:allow - deferred per test function
    import copy

    # import-placement:allow - deferred per test function
    from evals.render import render_html, render_markdown

    hostile = copy.deepcopy(report)
    payload = "<script>alert(1)</script> | `x` **y**"
    hostile["items"][0]["state"] = payload
    hostile["items"][0]["rationale"] = payload
    for miss in hostile["misses"]:
        miss["state"] = payload
        miss["rationale"] = payload
    html = render_html.render(hostile)
    markdown, _ = render_markdown.render(hostile)
    assert "<script>alert(1)" not in html
    # Fenced code renders literally; everywhere else the text must be escaped.
    outside_fences = re.sub(r"(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1$", "", markdown)
    assert "<script>alert(1)" not in outside_fences


def test_code_spans_and_fences_cannot_be_closed_early() -> None:
    # import-placement:allow - deferred per test function
    from evals.render.markup import md_code, md_fence

    def fence(text: str) -> int:
        length = 0
        while length < len(text) and text[length] == "`":
            length += 1
        return length

    def longest(value: str) -> int:
        return max((len(run) for run in re.findall(r"`+", value)), default=0)

    for value in ("plain", "a`b", "a``b", "````", "x `` y"):
        assert fence(md_code(value)) > longest(value), value
    for value in ("```\ncode\n```", "~~~~", "a`b"):
        assert fence(md_fence(value)) > longest(value), value


def _agent_run(directory: Path) -> Path:
    """Write a scripted agent-in-the-loop results file and its trace."""
    # import-placement:allow - deferred per test function
    from evals.agent import summary
    from evals.agent.scenarios import SCENARIOS

    records = []
    for condition in ("none", "full"):
        for trial in (1, 2):
            for scenario in SCENARIOS[:6]:
                consulted = condition == "full"
                records.append(
                    {
                        "model": "openrouter/test/model",
                        "condition": condition,
                        "trial": trial,
                        "scenario": scenario["id"],
                        "recipe": scenario["recipe"],
                        "kind": scenario["kind"],
                        "gold_action": scenario["gold_action"],
                        "valid": True,
                        "action_ok": consulted or trial == 1,
                        "consulted": consulted,
                        "before_act": consulted,
                        "recipe_fidelity": consulted or None,
                        "evidence": consulted or None,
                        "followed": consulted or None,
                        "asked": ["intent", "specific_enough"] if consulted else [],
                        "ember_calls": int(consulted),
                        "cost": 0.01,
                        "seconds": 5.0,
                        "steps": 2,
                        "timed_out": False,
                        "exit_code": 0,
                        "errors": [],
                        "stderr": "",
                    }
                )
    trace = directory / "agent_20261003T000000Z_trace.jsonl"
    trace.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    config = {
        "run_id": "agent_20261003T000000Z",
        "git_hash": "abc1234",
        "opencode": "test",
        "models": ["openrouter/test/model"],
        "conditions": ["none", "full"],
        "trials": 2,
        "scenarios": [s["id"] for s in SCENARIOS[:6]],
        "scenarios_snapshot": [
            {
                "id": s["id"],
                "recipe": s["recipe"],
                "gold_action": s["gold_action"],
                "rationale": s["rationale"],
                "prompt": s["prompt"],
            }
            for s in SCENARIOS[:6]
        ],
        "scenario_hash": hashlib.sha256(
            json.dumps(
                [
                    {
                        "id": s["id"],
                        "recipe": s["recipe"],
                        "gold_action": s["gold_action"],
                        "rationale": s["rationale"],
                        "prompt": s["prompt"],
                    }
                    for s in SCENARIOS[:6]
                ],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "trace": trace.name,
    }
    results = directory / "agent_20261003T000000Z_results.json"
    results.write_text(
        json.dumps({"config": config, "summary": summary.summarize(records)}),
        encoding="utf-8",
    )
    return results


def test_export_with_an_agent_run_leads_with_the_agent_section(
    synthetic_run: Path, tmp_path: Path
) -> None:
    # import-placement:allow - deferred per test function
    from evals import export

    out = export.export(synthetic_run, tmp_path / "bundle", _agent_run(tmp_path))
    html = (out / "report.html").read_text(encoding="utf-8")
    markdown = (out / "report.md").read_text(encoding="utf-8")
    assert '<section id="agent"' in html
    assert markdown.index('<a id="agent">') < markdown.index('<a id="context">')
    assert "## 2. Agent in the loop" in markdown
    assert (out / "data" / "agent_trace.jsonl").is_file()
    assert (out / "figures" / "agent-value.svg").is_file()
    assert (out / "figures" / "agent-flow.svg").is_file()


def test_flow_diagrams_have_text_versions(bundle: Path) -> None:
    # import-placement:allow - deferred per test function
    from evals import report_text

    markdown = (bundle / "report.md").read_text(encoding="utf-8")
    html = (bundle / "report.html").read_text(encoding="utf-8")
    first_line = report_text.ARCHITECTURE_TEXT.splitlines()[0]
    assert f"```text\n{first_line}" in markdown
    assert 'class="fig-text"' in html
