"""Mechanical integrity audit for the project vault (``vault/``).

Every note outside ``_meta/`` must carry valid frontmatter, use tags from
``_meta/tags.md`` with the right cardinality, resolve its wikilinks and
``code-refs``, and be reachable from the hub note (constitution Article IX).
The checks follow the wellspring vault audit.

Usage: .venv/bin/python scripts/vault_audit.py [VAULT_DIR]   (exit 1 on findings)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

DEFAULT_VAULT: Final = Path(__file__).resolve().parents[1] / "vault"
HUB_NAME: Final = "ember"
META_DIR: Final = "_meta"
IGNORED_DIRS: Final = frozenset({".obsidian", ".trash"})
FRONTMATTER_RE: Final = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
WIKILINK_RE: Final = re.compile(r"\[\[([^\]|#]+)[^\]]*\]\]")
VOCABULARY_RE: Final = re.compile(r"`((?:type|domain|status)/[a-z0-9-]+)`")


class Rule(StrEnum):
    """What a finding violates; printed first so the output is easy to filter."""

    FRONTMATTER = "frontmatter"
    UNKNOWN_TAG = "unknown-tag"
    TAG_CARDINALITY = "tag-cardinality"
    TYPE_MISMATCH = "type-mismatch"
    BROKEN_WIKILINK = "broken-wikilink"
    BROKEN_CODE_REF = "broken-code-ref"
    ORPHAN = "orphan"
    MISSING_HUB = "missing-hub"


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    rule: Rule
    detail: str


class Frontmatter(BaseModel):
    """The frontmatter contract every governed note satisfies."""

    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)

    title: str
    type: Literal["decision", "discovery", "session-log", "reference", "moc"]
    tags: list[str]
    created: date
    updated: date
    code_refs: list[str] = Field(default_factory=list, alias="code-refs")


@dataclass(frozen=True, slots=True)
class VaultIndex:
    """Every Markdown file in the vault, for resolving wikilinks like Obsidian."""

    root: Path
    by_name: Mapping[str, Path]

    def resolve(self, target: str) -> Path | None:
        """Resolve ``[[target]]`` as a vault-relative path, else by file name."""
        candidate = self.root / f"{target}.md"
        return candidate if candidate.is_file() else self.by_name.get(Path(target).name)


def links(text: str) -> list[str]:
    return [match.group(1).strip() for match in WIKILINK_RE.finditer(text)]


def tag_findings(
    path: Path, meta: Frontmatter, vocabulary: frozenset[str]
) -> list[Finding]:
    """Check tags against the vocabulary, the per-axis cardinality, and ``type``."""
    findings = [
        Finding(path, Rule.UNKNOWN_TAG, f"{tag} is not in {META_DIR}/tags.md")
        for tag in meta.tags
        if tag not in vocabulary
    ]
    counts = {
        axis: sum(tag.startswith(f"{axis}/") for tag in meta.tags)
        for axis in ("type", "domain", "status")
    }
    if counts["type"] != 1 or counts["domain"] < 1 or counts["status"] > 1:
        findings.append(
            Finding(
                path,
                Rule.TAG_CARDINALITY,
                f"needs one type/*, at least one domain/*, at most one status/*; "
                f"has {counts}",
            )
        )
    if f"type/{meta.type}" not in meta.tags:
        findings.append(
            Finding(
                path, Rule.TYPE_MISMATCH, f"type {meta.type} needs type/{meta.type}"
            )
        )
    return findings


def audit_note(
    path: Path, index: VaultIndex, vocabulary: frozenset[str]
) -> list[Finding]:
    """Return every problem with one note."""
    text = path.read_text(encoding="utf-8")
    findings = [
        Finding(path, Rule.BROKEN_WIKILINK, f"[[{target}]] does not resolve")
        for target in links(text)
        if index.resolve(target) is None
    ]
    header = FRONTMATTER_RE.match(text)
    if header is None:
        return [Finding(path, Rule.FRONTMATTER, "no YAML frontmatter"), *findings]
    try:
        meta = Frontmatter.model_validate(yaml.safe_load(header.group(1)))
    except (yaml.YAMLError, ValidationError) as exc:
        return [Finding(path, Rule.FRONTMATTER, " ".join(str(exc).split())), *findings]
    findings += [
        Finding(path, Rule.BROKEN_CODE_REF, f"{ref} does not exist")
        for ref in meta.code_refs
        if not (index.root.parent / ref).exists()
    ]
    return [*findings, *tag_findings(path, meta, vocabulary)]


def unreachable(hub: Path, notes: list[Path], index: VaultIndex) -> list[Path]:
    """Return the notes that no wikilink path from the hub reaches."""
    seen = {hub}
    queue = deque([hub])
    while queue:
        for target in links(queue.popleft().read_text(encoding="utf-8")):
            found = index.resolve(target)
            if found is not None and found not in seen:
                seen.add(found)
                queue.append(found)
    return [note for note in notes if note not in seen]


def audit(vault: Path) -> list[Finding]:
    """Run every check over the vault and return the findings."""
    root = vault.resolve()
    files = sorted(
        path
        for path in root.rglob("*.md")
        if IGNORED_DIRS.isdisjoint(path.relative_to(root).parts)
    )
    index = VaultIndex(root, {path.stem: path for path in files})
    notes = [path for path in files if path.relative_to(root).parts[0] != META_DIR]
    tags_file = root / META_DIR / "tags.md"
    vocabulary = frozenset(
        VOCABULARY_RE.findall(tags_file.read_text(encoding="utf-8"))
        if tags_file.is_file()
        else ()
    )
    findings = [
        found for note in notes for found in audit_note(note, index, vocabulary)
    ]
    hub = root / f"{HUB_NAME}.md"
    if not hub.is_file():
        return [*findings, Finding(hub, Rule.MISSING_HUB, "the hub note is missing")]
    return findings + [
        Finding(note, Rule.ORPHAN, f"no wikilink path from {hub.name} reaches it")
        for note in unreachable(hub, notes, index)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the project vault.")
    parser.add_argument("vault", nargs="?", type=Path, default=DEFAULT_VAULT)
    vault: Path = parser.parse_args(argv).vault
    if not vault.is_dir():
        print(f"vault not found: {vault}", file=sys.stderr)
        return 2
    findings = audit(vault)
    root = vault.resolve()
    for finding in findings:
        print(f"{finding.rule}: {finding.path.relative_to(root)}: {finding.detail}")
    print(
        f"vault audit: {len(findings)} finding(s)" if findings else "vault audit: clean"
    )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
