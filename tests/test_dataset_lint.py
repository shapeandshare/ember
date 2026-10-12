"""Dataset tooling: splitting, leakage, de-duplication, and the lint rules."""

from __future__ import annotations

from pathlib import Path

import pytest
from evals.dataset import dedup, leakage, lint, splitting
from evals.dataset.records.item import Item
from evals.dataset.records.lint_mode import LintMode
from evals.dataset.records.lint_rule import LintRule
from evals.dataset.records.split import Split

HASH64 = "c" * 64
QUESTIONS = {
    "owner": {
        "type": "choice",
        "instructions": "Which part of the system should handle this?",
        "criteria": {"api": "HTTP", "storage": "DB"},
    },
    "urgent": {"type": "noul", "instructions": "Is it urgent?"},
}


def item(
    item_id: str,
    *,
    split: str = "dev",
    owner: str = "api",
    urgent: bool = True,
    state: object = None,
    category: str = "routing",
    questions: dict | None = None,
    gold: dict | None = None,
    **extra: object,
) -> Item:
    source = extra.pop("source", {"kind": "authored", "dataset_version": HASH64})
    payload: dict[str, object] = {
        "id": item_id,
        "category": category,
        "split": split,
        "state": state if state is not None else f"error in {item_id}",
        "questions": questions or QUESTIONS,
        "gold_labels": gold if gold is not None else {"owner": owner, "urgent": urgent},
        "rationale": "constructed",
        "source": source,
        **extra,
    }
    return Item(**payload)  # type: ignore[arg-type]


# ###########################################################################
# splitting
# ###########################################################################


def test_assign_new_is_deterministic_and_moves_labels_toward_the_target() -> None:
    existing = [item(f"e{i}", split="test", owner="api") for i in range(6)]
    lock = {i.id: i.split for i in existing}
    new = [item(f"n{i}", owner="api") for i in range(4)]
    first = splitting.assign_new(existing + new, lock)
    second = splitting.assign_new(existing + new, dict(lock))
    assert first == second
    assert set(first) == {f"n{i}" for i in range(4)}
    # six test items and none in dev: the first new items must restore dev's 40% share
    assert first["n0"] is Split.dev
    assert all(i.id not in first or first[i.id] is lock[i.id] for i in existing)


def test_assign_new_keeps_families_together() -> None:
    parent = item("p1", split="test")
    child = item(
        "p1-para",
        source={"kind": "perturbed", "parent_id": "p1", "perturbation": "paraphrase"},
    )
    templated_a = item(
        "t1", source={"kind": "templated", "family": "fam", "template_version": "1"}
    )
    templated_b = item(
        "t2", source={"kind": "templated", "family": "fam", "template_version": "1"}
    )
    imported_a = item(
        "i1", source={"kind": "imported", "register_row": "src", "record_id": "r1"}
    )
    imported_b = item(
        "i2", source={"kind": "imported", "register_row": "src", "record_id": "r1"}
    )
    assigned = splitting.assign_new(
        [parent, child, templated_a, templated_b, imported_a, imported_b],
        {"p1": Split.test},
    )
    assert assigned["p1-para"] is Split.test
    assert assigned["t1"] is assigned["t2"]
    assert assigned["i1"] is assigned["i2"]


def test_lock_round_trips_and_only_appends(tmp_path: Path) -> None:
    lock_path = tmp_path / "splits.lock"
    splitting.append_lock(lock_path, {"a": Split.dev})
    splitting.append_lock(lock_path, {"b": Split.test})
    assert splitting.read_lock(lock_path) == {"a": Split.dev, "b": Split.test}
    with pytest.raises(ValueError, match="pinned"):
        splitting.append_lock(lock_path, {"a": Split.test})


# ###########################################################################
# leakage
# ###########################################################################


def _templated(item_id: str, split: str) -> Item:
    return item(
        item_id,
        split=split,
        source={"kind": "templated", "family": "f", "template_version": "1"},
    )


def _imported(item_id: str, split: str) -> Item:
    return item(
        item_id,
        split=split,
        source={"kind": "imported", "register_row": "s", "record_id": "x"},
    )


def test_leakage_flags_pin_changes_and_split_families() -> None:
    items = [
        item("a", split="dev"),
        item("b", split="test"),
        item(
            "b-var",
            split="dev",
            source={"kind": "perturbed", "parent_id": "b", "perturbation": "format"},
        ),
        item(
            "t1",
            split="dev",
            source={"kind": "templated", "family": "f", "template_version": "1"},
        ),
        item(
            "t2",
            split="test",
            source={"kind": "templated", "family": "f", "template_version": "1"},
        ),
        item(
            "i1",
            split="dev",
            source={"kind": "imported", "register_row": "s", "record_id": "x"},
        ),
        item(
            "i2",
            split="test",
            source={"kind": "imported", "register_row": "s", "record_id": "x"},
        ),
    ]
    lock = {i.id: i.split for i in items}
    lock["a"] = Split.test
    findings = leakage.check(items, lock)
    rules = {(f.rule, f.item_id) for f in findings}
    assert (LintRule.split_pinned, "a") in rules
    assert (LintRule.family_split, "b-var") in rules
    assert (LintRule.family_split, "t2") in rules or (
        LintRule.family_split,
        "t1",
    ) in rules
    assert (LintRule.family_split, "i2") in rules or (
        LintRule.family_split,
        "i1",
    ) in rules


def test_leakage_passes_a_consistent_dataset() -> None:
    items = [item("a"), item("b", split="test")]
    assert leakage.check(items, {"a": Split.dev, "b": Split.test}) == []


# ###########################################################################
# dedup
# ###########################################################################


def test_exact_duplicates_ignore_whitespace_and_case() -> None:
    items = [item("a", state="Error  in\nmodule"), item("b", state="error in module")]
    assert dedup.exact_duplicates(items) == [("a", "b")]


def test_near_duplicates_are_kept_only_when_gold_differs() -> None:
    base = " ".join(f"token{i}" for i in range(20))
    almost = base + " token20"
    same_gold = [item("a", state=base), item("b", state=almost)]
    assert dedup.near_duplicates(same_gold) == [("a", "b")]
    different_gold = [item("a", state=base), item("b", state=almost, owner="storage")]
    assert dedup.near_duplicates(different_gold) == []
    far = [item("a", state=base), item("c", state="completely unrelated words here")]
    assert dedup.near_duplicates(far) == []


# ###########################################################################
# lint
# ###########################################################################


def _rules(findings: list) -> set[LintRule]:  # type: ignore[type-arg]
    return {f.rule for f in findings}


def test_lint_reports_size_and_label_gaps_for_a_small_recipe() -> None:
    items = [item("a", split="dev", owner="api", urgent=True)]
    findings = lint.run(items, {"a": Split.dev})
    rules = _rules(findings)
    assert LintRule.size_target in rules
    assert LintRule.label_in_both_splits in rules
    assert LintRule.kind_shares in rules  # untagged items are a finding
    assert all(
        not f.enforced for f in findings if f.rule is not LintRule.no_live_secret
    )


def test_lint_enforce_all_marks_findings_enforced() -> None:
    items = [item("a")]
    findings = lint.run(items, {"a": Split.dev}, enforce_all=True)
    assert findings
    assert all(f.enforced for f in findings)


def test_lint_template_share_and_kind_shares_thresholds() -> None:
    templated = [
        item(
            f"t{i}",
            kind="positive",
            source={"kind": "templated", "family": f"f{i}", "template_version": "1"},
        )
        for i in range(4)
    ]
    authored = [item(f"a{i}", kind="positive") for i in range(6)]
    findings = lint.run(
        templated + authored, {i.id: i.split for i in templated + authored}
    )
    assert LintRule.template_share in _rules(findings)  # 40% > 30%
    assert any(
        f.rule is LintRule.kind_shares and "negative" in f.message for f in findings
    )


def test_lint_scale_and_dangerous_set_rules() -> None:
    score_q = {
        "sev": {
            "type": "score",
            "instructions": "How severe?",
            "criteria": ["Low", "Medium", "High"],
        }
    }
    unknown = item("s1", category="routing", questions=score_q, gold={"sev": 1})
    findings = lint.run([unknown], {"s1": Split.dev})
    assert LintRule.scale_declared in _rules(findings)


@pytest.mark.parametrize(
    "secret",
    [
        "AKIAABCDEFGHIJKLMNOP",
        "ghp_" + "x" * 36,
        "xoxb-1234-abcd",
        "AIza" + "y" * 35,
        "-----BEGIN RSA PRIVATE KEY-----",
        "eyJhbGciOi.eyJzdWIiOi.abc_def-ghi",
    ],
)
def test_no_live_secret_fails_even_in_report_mode(secret: str) -> None:
    items = [item("a", state={"command": f"export KEY={secret}"})]
    findings = lint.run(items, {"a": Split.dev})
    hits = [f for f in findings if f.rule is LintRule.no_live_secret]
    assert hits
    assert all(f.enforced for f in hits)
    assert lint.exit_code(findings) == 1


def test_no_live_secret_allows_documented_example_values() -> None:
    items = [
        item("a", state="aws configure set aws_access_key_id AKIAIOSFODNN7EXAMPLE")
    ]
    findings = lint.run(items, {"a": Split.dev})
    assert LintRule.no_live_secret not in _rules(findings)


def test_lint_mode_enforce_recipes_fail_the_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals.dataset import recipes

    strict = recipes.RECIPES["routing"].model_copy(update={"lint": LintMode.enforce})
    monkeypatch.setitem(recipes.RECIPES, "routing", strict)
    findings = lint.run([item("a")], {"a": Split.dev})
    assert any(f.enforced for f in findings if f.rule is LintRule.size_target)
    assert lint.exit_code(findings) == 1


def test_lint_passes_the_committed_dataset_in_report_mode() -> None:
    from evals.dataset import io
    from evals.dataset import splitting as sp

    items = io.read_items(io.DATASET_PATH)
    findings = lint.run(items, sp.read_lock(sp.LOCK_PATH))
    assert lint.exit_code(findings) == 0
    assert LintRule.no_live_secret not in _rules(findings)


def test_an_exemption_silences_that_kinds_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    """A documented exemption removes the kind's minimum-share finding."""
    from evals.dataset import io, recipes
    from evals.dataset import splitting as sp
    from evals.dataset.records.item_kind import ItemKind

    items = io.read_items(io.DATASET_PATH)
    lock = sp.read_lock(sp.LOCK_PATH)
    before = [
        finding
        for finding in lint.run(items, lock)
        if finding.rule is LintRule.kind_shares and finding.category == "routing"
    ]
    assert before, "the untagged dataset must have kind-share gaps"
    spec = recipes.RECIPES["routing"]
    silenced = spec.model_copy(
        update={"exemptions": {ItemKind.negative: "authored mainline set"}}
    )
    monkeypatch.setitem(recipes.RECIPES, "routing", silenced)
    after = [
        finding
        for finding in lint.run(items, lock)
        if finding.rule is LintRule.kind_shares and finding.category == "routing"
    ]
    assert len(after) == len(before) - 1
