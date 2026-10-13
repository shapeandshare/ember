"""The permanent FR-012 gate over every committed benchmark bundle (specs/004).

Recomputing a bundle's summary from its own trace reproduces the stored
per-recipe and per-question figures; vision recipes sit in the capability
panel; and the bundle's content hash equals the current dataset's, so the
source migration changed no scored content.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals import metrics
from evals.dataset import hashes, io

BENCHMARK = Path(__file__).resolve().parents[1] / "benchmark"
BUNDLES = sorted(p for p in BENCHMARK.glob("*/") if (p / "model.json").exists())


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_bundle_summary_is_reproducible_from_its_trace(bundle: Path) -> None:
    stored = json.loads((bundle / "results.json").read_text(encoding="utf-8"))[
        "summary"
    ]
    rows = [
        json.loads(line)
        for line in (bundle / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    recomputed = metrics.aggregate(rows)
    assert recomputed["categories"] == stored["categories"]
    assert recomputed["questions"] == stored["questions"]
    assert recomputed["overall"] == stored["overall"]


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_bundle_capability_holds_only_vision_recipes(bundle: Path) -> None:
    """Vision recipes never leak into ``overall``.

    A category-scoped bundle (a single-recipe re-run) may carry no capability
    panel at all; when it does, every listed category is a vision recipe.
    """
    summary = json.loads((bundle / "results.json").read_text(encoding="utf-8"))[
        "summary"
    ]
    capability = summary["capability"]
    if capability is not None:
        assert all(c.startswith("vision_") for c in capability["categories"])
    assert not any(
        c.startswith("vision_") for c in summary["overall"] if isinstance(c, str)
    )


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_bundle_meta_carries_the_phase_0_hashes(bundle: Path) -> None:
    meta = json.loads((bundle / "model.json").read_text(encoding="utf-8"))["meta"]
    assert meta["recipe_sha256"]
    assert isinstance(meta["tokens_available"], bool), (
        "every bundle records whether its trace carries token splits"
    )
    assert len(meta["dataset_content_sha256"]) == 64


def test_the_newest_bundle_carries_the_token_split() -> None:
    """A run against a current server records the token split.

    The Phase 0 harness refuses a server that omits it, so every new bundle has
    the splits; the two older bundles predate the requirement.
    """
    newest = max(
        BUNDLES,
        key=lambda b: json.loads((b / "model.json").read_text(encoding="utf-8"))[
            "meta"
        ]["run_at"],
    )
    meta = json.loads((newest / "model.json").read_text(encoding="utf-8"))["meta"]
    assert meta["tokens_available"] is True


def test_the_newest_bundle_is_on_the_current_dataset_version() -> None:
    """The source migration changed no scored content: the latest full run still
    hashes to the current dataset version. Older bundles scored a smaller item
    set and keep their own version."""
    current = hashes.dataset_content_sha256(io.read_items(io.DATASET_PATH))
    newest = max(
        BUNDLES,
        key=lambda b: json.loads((b / "model.json").read_text(encoding="utf-8"))[
            "meta"
        ]["run_at"],
    )
    meta = json.loads((newest / "model.json").read_text(encoding="utf-8"))["meta"]
    assert meta["dataset_content_sha256"] == current


def test_there_are_committed_bundles() -> None:
    assert len(BUNDLES) >= 2
