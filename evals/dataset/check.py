"""The provenance check (``ember eval dataset check``).

Every source resolves, the lock covers every item, the register and the
example-secret list validate, and the hashes compute.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from .hashes import dataset_content_sha256, recipe_hashes
from .io import DATASET_PATH, read_items
from .protocol import RULES, read_versions
from .records.example_secret import ExampleSecret
from .records.item import Item
from .records.register_row import RegisterRow
from .records.source_kind import SourceKind
from .records.split import Split
from .register import load, load_example_secrets, validate, validate_example_secrets
from .scales import SCALES
from .splitting import LOCK_PATH, read_lock

_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def run(
    items: Sequence[Item],
    lock: Mapping[str, Split],
    rows: Sequence[RegisterRow],
    examples: Sequence[ExampleSecret],
    *,
    versions: Sequence[str] | None = None,
) -> list[str]:
    """Return every provenance problem found; empty when the dataset is sound.

    Parameters
    ----------
    items : Sequence[Item]
        The dataset.
    lock : Mapping[str, Split]
        The committed split pins.
    rows : Sequence[RegisterRow]
        The data-source register.
    examples : Sequence[ExampleSecret]
        The example-secret list.
    versions : Sequence[str] | None
        The recorded dataset versions (``versions.lock`` when ``None``); the
        current content hash and every protocol rule's and scale's ``since``
        must be among them (FR-046).

    Returns
    -------
    list[str]
        Human-readable problems.
    """
    problems: list[str] = []
    ids = {item.id for item in items}
    for item in items:
        source = item.source
        if source.kind is SourceKind.mined and not _HEX40.match(source.commit or ""):
            problems.append(
                f"{item.id}: mined commit {source.commit!r} is not a 40-hex SHA"
            )
        if source.kind is SourceKind.perturbed and source.parent_id not in ids:
            problems.append(
                f"{item.id}: perturbed parent {source.parent_id!r} does not exist"
            )
        if item.id not in lock:
            problems.append(f"{item.id}: not in splits.lock")
    problems += validate(rows, items)
    try:
        validate_example_secrets(examples)
    except ValueError as exc:
        problems.append(str(exc))
    recipe_hashes(items)
    problems += version_problems(dataset_content_sha256(items), versions)
    return problems


def version_problems(current: str, versions: Sequence[str] | None) -> list[str]:
    """Check the dataset version and every protocol or rubric ``since`` are recorded."""
    recorded = set(read_versions() if versions is None else versions)
    problems: list[str] = []
    if current not in recorded:
        problems.append(
            f"dataset version {current[:12]} is not a recorded dataset version "
            "(versions.lock); run `ember eval dataset card` to record it"
        )
    for rule in RULES:
        if rule.since not in recorded:
            problems.append(
                f"protocol rule {rule.text[:40]!r}: since {rule.since[:12]} "
                "is not a recorded dataset version"
            )
    for (category, question), scale in SCALES.items():
        if scale.since not in recorded:
            problems.append(
                f"scale {category}/{question}: since {scale.since[:12]} "
                "is not a recorded dataset version"
            )
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    """Run the provenance check (``ember eval dataset check``)."""
    parser = argparse.ArgumentParser(prog="ember eval dataset check")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    args = parser.parse_args(argv)
    problems = run(
        read_items(args.dataset), read_lock(args.lock), load(), load_example_secrets()
    )
    for problem in problems:
        print(f"FAIL {problem}")
    print(f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
