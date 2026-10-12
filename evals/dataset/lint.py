"""The dataset lint with report and enforce modes (specs/004 FR-035, FR-044).

Rules cover composition, size, direction, provenance, leakage, and the
credential guard.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from . import dedup, leakage
from .anchors import validate_anchors
from .io import DATASET_PATH, read_items
from .recipes import RECIPES
from .records.example_secret import ExampleSecret
from .records.item import Item
from .records.item_kind import ItemKind
from .records.lint_finding import LintFinding
from .records.lint_mode import LintMode
from .records.lint_rule import LintRule
from .records.register_row import RegisterRow
from .records.source_kind import SourceKind
from .records.split import Split
from .records.verdict import Verdict
from .register import load, load_example_secrets
from .scales import scale_for
from .secret_guard import no_live_secret
from .splitting import LOCK_PATH, read_lock

SIZE_TARGET = 300
RISK_SIZE_TARGET = 400
TEST_LABEL_MINIMUM = 40
TEMPLATE_SHARE_MAX = 0.30
KIND_SHARES: Mapping[ItemKind, float] = {
    ItemKind.negative: 0.20,
    ItemKind.control: 0.10,
    ItemKind.hard_negative: 0.15,
    ItemKind.near_miss: 0.10,
    ItemKind.adversarial: 0.05,
    ItemKind.insufficient_context: 0.05,
    ItemKind.variant: 0.10,
    ItemKind.long_tier: 0.10,
}
LOG_OR_DIFF_RECIPES = frozenset({"failure_triage", "change_risk"})


def _finding(
    rule: LintRule, category: str, message: str, enforced: bool
) -> LintFinding:
    return LintFinding(rule=rule, category=category, message=message, enforced=enforced)


def recipe_rules(
    category: str,
    rows: Sequence[Item],
    *,
    enforced: bool,
) -> list[LintFinding]:
    """Apply the per-recipe rules (size, labels, kinds, template share, scales)."""
    spec = RECIPES.get(category)
    findings: list[LintFinding] = []
    target = RISK_SIZE_TARGET if spec is not None and spec.risk else SIZE_TARGET
    if len(rows) < target:
        findings.append(
            _finding(
                LintRule.size_target,
                category,
                f"{category}: {len(rows)} items, target {target}",
                enforced,
            )
        )
    per_label: dict[tuple[str, str], Counter[Split]] = defaultdict(Counter)
    for item in rows:
        for qid, gold in item.gold_labels.items():
            per_label[(qid, json.dumps(gold, sort_keys=True))][item.split] += 1
    for (qid, label), counts in sorted(per_label.items()):
        if counts[Split.dev] == 0 or counts[Split.test] == 0:
            findings.append(
                _finding(
                    LintRule.label_in_both_splits,
                    category,
                    f"{category}: {qid}={label} is missing from a split",
                    enforced,
                )
            )
        elif counts[Split.test] < TEST_LABEL_MINIMUM:
            findings.append(
                _finding(
                    LintRule.label_in_both_splits,
                    category,
                    f"{category}: {qid}={label} has {counts[Split.test]} test items, "
                    f"minimum {TEST_LABEL_MINIMUM}",
                    enforced,
                )
            )
    findings += kind_shares(category, rows, enforced=enforced)
    templated = sum(1 for item in rows if item.source.kind is SourceKind.templated)
    if rows and templated / len(rows) > TEMPLATE_SHARE_MAX:
        findings.append(
            _finding(
                LintRule.template_share,
                category,
                f"{category}: {templated} of {len(rows)} items are templated "
                f"({templated / len(rows):.0%} > {TEMPLATE_SHARE_MAX:.0%})",
                enforced,
            )
        )
    findings += scale_rules(category, rows)
    return findings


def kind_shares(
    category: str, rows: Sequence[Item], *, enforced: bool
) -> list[LintFinding]:
    """Check every item kind's minimum share, honouring documented exemptions."""
    spec = RECIPES.get(category)
    exemptions = spec.exemptions if spec is not None else {}
    counts = Counter(item.kind for item in rows)
    findings: list[LintFinding] = []
    untagged = counts.get(None, 0)
    if untagged:
        findings.append(
            _finding(
                LintRule.kind_shares,
                category,
                f"{category}: {untagged} of {len(rows)} items have no kind",
                enforced,
            )
        )
    score_items = sum(
        1 for item in rows if any(q["type"] == "score" for q in item.questions.values())
    )
    for kind, minimum in KIND_SHARES.items():
        if kind in exemptions:
            continue
        if kind is ItemKind.long_tier and category not in LOG_OR_DIFF_RECIPES:
            continue
        base = score_items if kind is ItemKind.near_miss else len(rows)
        if base == 0:
            continue
        share = counts.get(kind, 0) / base
        if share < minimum:
            findings.append(
                _finding(
                    LintRule.kind_shares,
                    category,
                    f"{category}: {kind.value} is {share:.0%} of {base}, "
                    f"minimum {minimum:.0%}",
                    enforced,
                )
            )
    return findings


def scale_rules(category: str, rows: Sequence[Item]) -> list[LintFinding]:
    """Score questions declare matching scales; risk recipes declare unsafe sets.

    These rules are always enforced (FR-003a), whatever the recipe's lint mode.
    """
    findings: list[LintFinding] = []
    if not rows:
        return findings
    spec = RECIPES.get(category)
    for qid, question in rows[0].questions.items():
        if question["type"] == "score":
            scale = scale_for(category, qid)
            criteria = question["criteria"]
            if scale is None or criteria[0] != scale.low or criteria[-1] != scale.high:
                findings.append(
                    _finding(
                        LintRule.scale_declared,
                        category,
                        f"{category}/{qid}: no scale declared or poles differ",
                        True,
                    )
                )
            if scale is not None:
                for problem in validate_anchors(scale, criteria):
                    findings.append(
                        _finding(LintRule.scale_anchored, category, problem, True)
                    )
            if (
                spec is not None
                and spec.risk
                and (scale is None or scale.dangerous_from is None)
            ):
                findings.append(
                    _finding(
                        LintRule.dangerous_set_declared,
                        category,
                        f"{category}/{qid}: risk recipe without a dangerous end",
                        True,
                    )
                )
        if question["type"] == "choice" and spec is not None and spec.risk:
            if qid not in spec.dangerous_options:
                findings.append(
                    _finding(
                        LintRule.dangerous_set_declared,
                        category,
                        f"{category}/{qid}: risk recipe without dangerous options",
                        True,
                    )
                )
    return findings


def source_rules(
    items: Sequence[Item], rows: Sequence[RegisterRow]
) -> list[LintFinding]:
    """Every source reference resolves: parents exist, imported rows are ``used``."""
    by_id = {item.id for item in items}
    register = {row.id: row for row in rows}
    findings: list[LintFinding] = []
    for item in items:
        source = item.source
        problem: str | None = None
        if source.kind is SourceKind.perturbed and source.parent_id not in by_id:
            problem = f"parent {source.parent_id!r} does not exist"
        if source.kind is SourceKind.imported:
            row = register.get(source.register_row or "")
            if row is None:
                problem = f"register row {source.register_row!r} does not exist"
            elif row.verdict is not Verdict.used:
                problem = f"register row {source.register_row!r} is {row.verdict.value}"
        if problem:
            findings.append(
                LintFinding(
                    rule=LintRule.source_resolves,
                    category=item.category,
                    item_id=item.id,
                    message=f"{item.id}: {problem}",
                    enforced=True,
                )
            )
    return findings


def duplicate_rules(items: Sequence[Item]) -> list[LintFinding]:
    """Exact duplicates, and near-duplicates with identical gold."""
    by_id = {item.id: item for item in items}
    findings: list[LintFinding] = []
    for a, b in dedup.exact_duplicates(items):
        findings.append(
            LintFinding(
                rule=LintRule.near_duplicate_gold,
                category=by_id[b].category,
                item_id=b,
                message=f"{b} duplicates {a} exactly",
                enforced=True,
            )
        )
    for a, b in dedup.near_duplicates(items):
        findings.append(
            LintFinding(
                rule=LintRule.near_duplicate_gold,
                category=by_id[b].category,
                item_id=b,
                message=f"{b} nearly duplicates {a} with the same gold",
                enforced=True,
            )
        )
    return findings


def run(
    items: Sequence[Item],
    lock: Mapping[str, Split],
    rows: Sequence[RegisterRow] | None = None,
    examples: Sequence[ExampleSecret] | None = None,
    *,
    enforce_all: bool = False,
) -> list[LintFinding]:
    """Run every rule and return the findings.

    Parameters
    ----------
    items : Sequence[Item]
        The dataset.
    lock : Mapping[str, Split]
        The committed split pins.
    rows : Sequence[RegisterRow] | None
        The data-source register (loaded from disk when ``None``).
    examples : Sequence[ExampleSecret] | None
        The example-secret list (loaded from disk when ``None``).
    enforce_all : bool
        Treat every recipe as ``LintMode.enforce``.

    Returns
    -------
    list[LintFinding]
        Findings; ``enforced`` ones fail the build (see ``exit_code``).
    """
    register_rows = load() if rows is None else rows
    example_values = load_example_secrets() if examples is None else examples
    by_recipe: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        by_recipe[item.category].append(item)
    findings: list[LintFinding] = []
    for category, recipe_items in sorted(by_recipe.items()):
        spec = RECIPES.get(category)
        enforced = enforce_all or (spec is not None and spec.lint is LintMode.enforce)
        findings += recipe_rules(category, recipe_items, enforced=enforced)
    findings += source_rules(items, register_rows)
    findings += duplicate_rules(items)
    findings += leakage.check(items, lock)
    findings += no_live_secret(items, example_values)
    return findings


def exit_code(findings: Sequence[LintFinding]) -> int:
    """Return 1 when any finding is enforced, else 0."""
    return 1 if any(finding.enforced for finding in findings) else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Lint the dataset (``ember eval dataset lint``)."""
    parser = argparse.ArgumentParser(prog="ember eval dataset lint")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    parser.add_argument("--enforce-all", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    findings = run(
        read_items(args.dataset), read_lock(args.lock), enforce_all=args.enforce_all
    )
    if args.as_json:
        print(json.dumps([f.model_dump(mode="json") for f in findings], indent=2))
    else:
        for finding in findings:
            flag = "FAIL" if finding.enforced else "gap "
            print(f"{flag} {finding.rule.value:<24} {finding.message}")
        enforced = sum(1 for f in findings if f.enforced)
        print(f"{len(findings)} findings, {enforced} enforced")
    return exit_code(findings)


if __name__ == "__main__":
    raise SystemExit(main())
