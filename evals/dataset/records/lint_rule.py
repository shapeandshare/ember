"""LintRule: The rules the dataset lint checks."""

from __future__ import annotations

from enum import StrEnum


class LintRule(StrEnum):
    """The rules the dataset lint checks."""

    size_target = "size-target"
    label_in_both_splits = "label-in-both-splits"
    kind_shares = "kind-shares"
    template_share = "template-share"
    scale_declared = "scale-declared"
    dangerous_set_declared = "dangerous-set-declared"
    scale_anchored = "scale-anchored"
    source_resolves = "source-resolves"
    family_split = "family-split"
    split_pinned = "split-pinned"
    near_duplicate_gold = "near-duplicate-gold"
    no_live_secret = "no-live-secret"  # noqa: S105 - a rule name, not a credential
