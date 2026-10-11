"""Leakage checks: pinned splits and families that must not straddle dev and test."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from .records.item import Item
from .records.lint_finding import LintFinding
from .records.lint_rule import LintRule
from .records.source_kind import SourceKind
from .records.split import Split


def _family_groups(items: Sequence[Item]) -> dict[str, list[Item]]:
    groups: dict[str, list[Item]] = defaultdict(list)
    by_id = {item.id: item for item in items}
    for item in items:
        source = item.source
        if source.kind is SourceKind.perturbed and source.parent_id:
            groups[f"parent:{source.parent_id}"].append(item)
            parent = by_id.get(source.parent_id)
            if (
                parent is not None
                and parent not in groups[f"parent:{source.parent_id}"]
            ):
                groups[f"parent:{source.parent_id}"].append(parent)
        elif source.kind is SourceKind.templated and source.family:
            groups[f"template:{source.family}"].append(item)
        elif source.kind is SourceKind.imported and source.register_row:
            groups[f"record:{source.register_row}:{source.record_id}"].append(item)
    return groups


def check(items: Sequence[Item], lock: Mapping[str, Split]) -> list[LintFinding]:
    """Return findings for moved pins and families split across dev and test.

    Parameters
    ----------
    items : Sequence[Item]
        The dataset.
    lock : Mapping[str, Split]
        The committed pins.

    Returns
    -------
    list[LintFinding]
        ``split-pinned`` and ``family-split`` findings; empty when clean.
    """
    findings: list[LintFinding] = []
    for item in items:
        pinned = lock.get(item.id)
        if pinned is not None and pinned is not item.split:
            findings.append(
                LintFinding(
                    rule=LintRule.split_pinned,
                    category=item.category,
                    item_id=item.id,
                    message=(
                        f"{item.id} is {item.split.value} but splits.lock pins it "
                        f"to {pinned.value}"
                    ),
                    enforced=True,
                )
            )
    for name, members in _family_groups(items).items():
        splits = {member.split for member in members}
        if len(splits) > 1:
            for member in members:
                findings.append(
                    LintFinding(
                        rule=LintRule.family_split,
                        category=member.category,
                        item_id=member.id,
                        message=f"family {name} straddles dev and test",
                        enforced=True,
                    )
                )
    return findings
