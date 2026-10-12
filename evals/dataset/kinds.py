"""Audit ``Item.kind`` coverage against the composition rule (report mode)."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .io import DATASET_PATH, read_items
from .lint import kind_shares
from .records.item import Item


def audit(items: Sequence[Item]) -> dict[str, dict[str, Any]]:
    """Return per-recipe kind counts, untagged counts, and the lint's gaps.

    Parameters
    ----------
    items : Sequence[Item]
        The dataset.

    Returns
    -------
    dict[str, dict[str, Any]]
        Keyed by recipe: ``items``, ``kinds`` (counts per kind, ``untagged``
        included), ``untagged``, and ``gaps`` — the kind-shares findings the
        lint reports (minima and exemptions are the lint's rules; this tool
        never re-implements them).
    """
    by_recipe: dict[str, list[Item]] = {}
    for item in items:
        by_recipe.setdefault(item.category, []).append(item)
    report: dict[str, dict[str, Any]] = {}
    for category, rows in sorted(by_recipe.items()):
        counts = Counter(
            item.kind.value if item.kind else "untagged" for item in rows
        )
        report[category] = {
            "items": len(rows),
            "kinds": dict(sorted(counts.items())),
            "untagged": counts.get("untagged", 0),
            "gaps": [
                finding.message
                for finding in kind_shares(category, rows, enforced=False)
            ],
        }
    return report


def render(report: dict[str, dict[str, Any]]) -> str:
    """Render the audit as one line per recipe, naming its gaps."""
    lines: list[str] = []
    for category, entry in report.items():
        gaps = "; ".join(entry["gaps"]) if entry["gaps"] else "none"
        lines.append(
            f"{category}: {entry['items']} items, untagged {entry['untagged']}; "
            f"gaps: {gaps}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry: ``ember eval dataset kind [--dataset PATH] [--json]``."""
    parser = argparse.ArgumentParser(prog="ember eval dataset kind")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = audit(read_items(args.dataset))
    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render(report))
    return 0
