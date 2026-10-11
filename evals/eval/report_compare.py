"""``ember eval report --compare``: two runs side by side, B minus A.

Runs are comparable when they scored the same dataset version (the content
hash, FR-034); runs from before content hashing fall back to the file hash.
"""

from __future__ import annotations

from typing import Any

from .report_markdown import DASH, num, pct, table


def _delta(a: float | None, b: float | None, *, percent: bool) -> str:
    if a is None or b is None:
        return DASH
    return f"{(b - a) * 100:+.1f} pts" if percent else f"{b - a:+.3f}"


COMPARED = (
    ("Question accuracy ↑", "overall", "accuracy", True),
    ("Items fully correct ↑", "overall", "item_accuracy", True),
    ("choice accuracy ↑", "choice", "accuracy", True),
    ("choice ECE ↓", "choice", "ece", False),
    ("choice Brier ↓", "choice", "brier", False),
    ("noul accuracy ↑", "noul", "accuracy", True),
    ("noul ECE ↓", "noul", "ece", False),
    ("noul Brier ↓", "noul", "brier", False),
    ("score accuracy ↑", "score", "accuracy", True),
    ("score MAE ↓", "score", "mae", False),
    ("score RPS ↓", "score", "rps", False),
)


def render_compare(a: dict[str, Any], b: dict[str, Any]) -> str:
    """Two runs side by side, B minus A."""
    cfg_a, cfg_b = a["config"], b["config"]
    sum_a, sum_b = a["summary"], b["summary"]
    out = [
        "## ember benchmark: comparison",
        "",
        f"A `{cfg_a['run_id']}` (git `{cfg_a['git_hash']}`) · "
        f"B `{cfg_b['run_id']}` (git `{cfg_b['git_hash']}`)",
        "",
    ]
    # Two runs are comparable when they scored the same dataset version (the
    # content hash); annotation-only edits change the file hash but not the
    # version. Runs from before content hashing fall back to the file hash.
    version_key = (
        "dataset_content_sha256"
        if cfg_a.get("dataset_content_sha256") and cfg_b.get("dataset_content_sha256")
        else "dataset_sha256"
    )
    if any(cfg_a.get(k) != cfg_b.get(k) for k in (version_key, "split", "category")):
        out += [
            "**Warning:** the runs scored different item sets (dataset, split, or "
            "category differs), so these deltas are not comparable.",
            "",
        ]
    rows = []
    for label, section, key, percent in COMPARED:
        value_a = (sum_a.get(section) or {}).get(key)
        value_b = (sum_b.get(section) or {}).get(key)
        fmt = pct if percent else num
        rows.append(
            [
                label,
                fmt(value_a),
                fmt(value_b),
                _delta(value_a, value_b, percent=percent),
            ]
        )
    for qid in dict.fromkeys([*sum_a["questions"], *sum_b["questions"]]):
        value_a = sum_a["questions"].get(qid, {}).get("accuracy")
        value_b = sum_b["questions"].get(qid, {}).get("accuracy")
        rows.append(
            [
                f"{qid} accuracy ↑",
                pct(value_a),
                pct(value_b),
                _delta(value_a, value_b, percent=True),
            ]
        )
    out += table(["Metric", "A", "B", "Δ (B-A)"], rows)
    return "\n".join(out)
