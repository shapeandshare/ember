"""The generated dataset card (``card.json`` and ``CARD.md``), never hand-written."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..atomic import write_atomic
from .hashes import dataset_content_sha256, recipe_hashes, register_sha256
from .io import DATASET_PATH, read_items
from .lint import run as run_lint
from .protocol import RULES, record_version
from .recipes import RECIPES
from .records.item import Item
from .records.lint_finding import LintFinding
from .records.register_row import RegisterRow
from .records.source_kind import SourceKind
from .records.split import Split
from .records.stability_result import StabilityResult
from .register import REGISTER_PATH, load
from .scales import SCALES
from .splitting import LOCK_PATH, read_lock
from .stability import SINGLE_RATER, compute, load_rounds

DATASET_DIR = Path(__file__).resolve().parent
CARD_JSON = DATASET_DIR / "card.json"
CARD_MD = DATASET_DIR / "CARD.md"


def _acted_differs_share(rows: Sequence[Item]) -> float | None:
    """Share of captured items whose reviewed choice differs from what was done."""
    captured = [item for item in rows if item.source.kind is SourceKind.captured]
    if not captured:
        return None
    return round(sum(1 for item in captured if item.acted_differs) / len(captured), 4)


def _recipe_card(
    category: str,
    rows: Sequence[Item],
    register: Sequence[RegisterRow],
    findings: Sequence[LintFinding],
    recipe_hash: str,
    stability: StabilityResult | None,
) -> dict[str, Any]:
    spec = RECIPES.get(category)
    per_label: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"dev": 0, "test": 0})
    )
    for item in rows:
        for qid, gold in item.gold_labels.items():
            per_label[qid][json.dumps(gold)][item.split.value] += 1
    kinds = Counter(item.kind.value if item.kind else "untagged" for item in rows)
    sources = Counter(item.source.kind.value for item in rows)
    used_rows = {
        item.source.register_row
        for item in rows
        if item.source.kind in (SourceKind.imported, SourceKind.mined)
        and item.source.register_row
    }
    external = [
        {
            "id": row.id,
            "name": row.name,
            "licence": row.licence.reading,
            "licence_class": row.licence.class_.value,
            "permission": row.permission,
            "attribution": row.attribution,
            "snapshot": (
                {"version": row.snapshot.version, "sha256": row.snapshot.sha256}
                if row.snapshot
                else None
            ),
            "mirror": (
                {
                    "location": row.mirror.location,
                    "sha256": row.mirror.sha256,
                    "public": row.mirror.public,
                }
                if row.mirror
                else None
            ),
        }
        for row in register
        if row.id in used_rows
    ]
    return {
        "items": len(rows),
        "dev": sum(1 for i in rows if i.split is Split.dev),
        "test": sum(1 for i in rows if i.split is Split.test),
        "per_label_per_split": {
            qid: dict(labels.items()) for qid, labels in sorted(per_label.items())
        },
        "kind_shares": dict(sorted(kinds.items())),
        "source_shares": dict(sorted(sources.items())),
        "easy_items": sum(1 for i in rows if i.tier == "easy"),
        "external_sources": external,
        "label_stability": stability.model_dump() if stability else None,
        "inter_source_agreement": None,
        "rater_count": 1,
        "second_review_pending": sum(1 for i in rows if i.second_review),
        "acted_differs_share": _acted_differs_share(rows),
        "recipe_sha256": recipe_hash,
        "gaps": [
            f.message for f in findings if f.category == category and not f.enforced
        ],
        "exemptions": (
            {kind.value: reason for kind, reason in spec.exemptions.items()}
            if spec
            else {}
        ),
        "lint": spec.lint.value if spec else None,
        "family": spec.family.value if spec else None,
        "risk": spec.risk if spec else False,
        "rubric_since": {
            question: scale.since
            for (scale_category, question), scale in sorted(SCALES.items())
            if scale_category == category
        },
    }


def build(
    items: Sequence[Item],
    register: Sequence[RegisterRow],
    findings: Sequence[LintFinding],
    *,
    register_sha256: str | None,
    generated_from: str = DATASET_PATH.name,
    stability: dict[str, StabilityResult] | None = None,
) -> dict[str, Any]:
    """Build the card from the dataset, the register, and the lint findings.

    Parameters
    ----------
    items : Sequence[Item]
        The dataset.
    register : Sequence[RegisterRow]
        The data-source register.
    findings : Sequence[LintFinding]
        The lint's findings (report-mode ones become each recipe's ``gaps``).
    register_sha256 : str | None
        The register file's hash, or ``None`` when there is no register.
    generated_from : str
        The dataset file name recorded in the card.
    stability : dict[str, StabilityResult] | None, optional
        The computed label stability per recipe, when rounds exist.

    Returns
    -------
    dict[str, Any]
        The card.
    """
    by_recipe: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        by_recipe[item.category].append(item)
    hashes = recipe_hashes(items)
    rounds = stability or {}
    return {
        "generated_from": generated_from,
        "dataset_content_sha256": dataset_content_sha256(items),
        "register_sha256": register_sha256,
        "items": len(items),
        "protocol": [rule.model_dump() for rule in RULES],
        "recipes": {
            category: _recipe_card(
                category,
                rows,
                register,
                findings,
                hashes[category],
                rounds.get(category),
            )
            for category, rows in sorted(by_recipe.items())
        },
    }


def _stability_line(value: dict[str, Any] | None) -> str:
    """Render a recipe's label stability for the Markdown card."""
    if not value:
        return "none yet"
    return (
        f"agreement {value['agreement']:.0%}, unstable {len(value['unstable'])},"
        f" rater count {value['rater_count']}"
    )


def _agreement_line(value: float | None) -> str:
    """Render inter-source agreement, naming why it is absent when it is."""
    if value is None:
        return "none yet (no imports)"
    return f"{value:.0%}"


def render_markdown(card: dict[str, Any]) -> str:
    """Render the card as Markdown; deterministic for a given card."""
    lines = [
        "# Dataset card",
        "",
        "Generated by `ember eval dataset card`; do not edit by hand.",
        "",
        f"- Items: {card['items']}",
        f"- Dataset version (content hash): `{card['dataset_content_sha256']}`",
        f"- Register hash: `{card['register_sha256']}`",
        "",
        "Labelling protocol (each rule since the dataset version it first applies to):",
        *[
            f"- {rule['text']} (since `{rule['since'][:12]}`)"
            for rule in card["protocol"]
        ],
        "",
        SINGLE_RATER,
        "",
    ]
    for category, recipe in card["recipes"].items():
        lines += [
            f"## `{category}`",
            "",
            f"- Items: {recipe['items']} (dev {recipe['dev']}, test {recipe['test']}); "
            f"family `{recipe['family']}`; risk {recipe['risk']}; "
            f"lint `{recipe['lint']}`",
            f"- Recipe hash: `{recipe['recipe_sha256']}`",
            f"- Rubric anchors since: {json.dumps(recipe['rubric_since'])}",
            f"- Kinds: {json.dumps(recipe['kind_shares'])}",
            f"- Sources: {json.dumps(recipe['source_shares'])}",
            f"- Easy items: {recipe['easy_items']}; "
            f"rater count {recipe['rater_count']}; "
            f"second review pending {recipe['second_review_pending']}",
            f"- Label stability: {_stability_line(recipe['label_stability'])}; "
            f"inter-source agreement: "
            f"{_agreement_line(recipe['inter_source_agreement'])}; acted-differs "
            f"share: {recipe['acted_differs_share']}",
            "",
            "| Question | Label | dev | test |",
            "| --- | --- | --- | --- |",
        ]
        for qid, labels in recipe["per_label_per_split"].items():
            for label, counts in labels.items():
                lines.append(
                    f"| `{qid}` | `{label}` | {counts['dev']} | {counts['test']} |"
                )
        lines.append("")
        if recipe["external_sources"]:
            lines.append("External sources:")
            for source in recipe["external_sources"]:
                lines.append(
                    f"- `{source['id']}` — {source['name']}; licence "
                    f"`{source['licence_class']}`: {source['licence']}"
                )
                if source.get("permission"):
                    lines.append(f"  - Permission: {source['permission']}")
                if source.get("snapshot"):
                    snapshot = source["snapshot"]
                    lines.append(
                        f"  - Snapshot `{snapshot['version']}` "
                        f"sha256 `{snapshot['sha256']}`"
                    )
                if source.get("mirror"):
                    mirror = source["mirror"]
                    lines.append(
                        f"  - Mirror `{mirror['location']}` "
                        f"sha256 `{mirror['sha256']}` (public: {mirror['public']})"
                    )
                if source.get("attribution"):
                    lines.append(f"  - Attribution: {source['attribution']}")
            lines.append("")
        if recipe["exemptions"]:
            lines.append("Exemptions:")
            for kind, reason in recipe["exemptions"].items():
                lines.append(f"- `{kind}`: {reason}")
            lines.append("")
        lines.append("Gaps:" if recipe["gaps"] else "Gaps: none")
        lines += [f"- {gap}" for gap in recipe["gaps"]]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def current(dataset_path: Path = DATASET_PATH) -> dict[str, Any]:
    """Build the card for the dataset on disk."""
    items = read_items(dataset_path)
    register = load()
    findings = run_lint(items, read_lock(LOCK_PATH), register)
    digest = register_sha256(REGISTER_PATH) if REGISTER_PATH.exists() else None
    stability = compute(load_rounds()) if dataset_path == DATASET_PATH else None
    return build(
        items,
        register,
        findings,
        register_sha256=digest,
        generated_from=dataset_path.name,
        stability=stability,
    )


def write(card: dict[str, Any]) -> None:
    """Write ``card.json`` and ``CARD.md`` atomically."""
    write_atomic(CARD_JSON, json.dumps(card, indent=2, ensure_ascii=False) + "\n")
    write_atomic(CARD_MD, render_markdown(card))


def is_fresh(card: dict[str, Any]) -> bool:
    """Return whether the committed card files equal ``card``."""
    if not CARD_JSON.exists() or not CARD_MD.exists():
        return False
    expected_json = json.dumps(card, indent=2, ensure_ascii=False) + "\n"
    return CARD_JSON.read_text(encoding="utf-8") == expected_json and CARD_MD.read_text(
        encoding="utf-8"
    ) == render_markdown(card)


def main(argv: Sequence[str] | None = None) -> int:
    """Regenerate or check the card (``ember eval dataset card``)."""
    parser = argparse.ArgumentParser(prog="ember eval dataset card")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    card = current(args.dataset)
    if args.check:
        if is_fresh(card):
            print("dataset card is fresh")
            return 0
        print("dataset card is stale; run `ember eval dataset card`")
        return 1
    write(card)
    print(f"wrote {CARD_JSON} and {CARD_MD}")
    if args.dataset == DATASET_PATH and record_version(card["dataset_content_sha256"]):
        print(f"recorded dataset version {card['dataset_content_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
