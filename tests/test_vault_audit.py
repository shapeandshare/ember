"""The vault audit keeps vault/ navigable; these tests pin every rule it enforces."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "vault_audit.py"


def _load_audit() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vault_audit", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_audit()

TAGS = """\
# Tags

`type/decision` `type/moc` `domain/runtime` `domain/governance`
`status/draft` `status/stale`
"""


def note(
    note_type: str, tags: list[str], body: str = "Part of [[ember]].", extra: str = ""
) -> str:
    lines = ["---", "title: A note", f"type: {note_type}", "tags:"]
    lines += [f"  - {tag}" for tag in tags]
    lines += ["created: 2026-10-02", "updated: 2026-10-02"]
    lines += [extra] if extra else []
    return "\n".join([*lines, "---", "", "# A note", "", body, ""])


DECISION = note("decision", ["type/decision", "domain/runtime"])


def make_vault(root: Path, notes: dict[str, str], *, linked: bool = True) -> Path:
    vault = root / "vault"
    (vault / "_meta").mkdir(parents=True)
    (vault / "_meta" / "tags.md").write_text(TAGS, encoding="utf-8")
    links = "\n".join(f"- [[{Path(name).stem}]]" for name in notes) if linked else ""
    hub = note("moc", ["type/moc", "domain/governance"], body=links)
    (vault / "ember.md").write_text(hub, encoding="utf-8")
    for name, text in notes.items():
        path = vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return vault


def rules(vault: Path) -> set[tuple[str, str]]:
    root = vault.resolve()
    return {
        (f.path.relative_to(root).as_posix(), str(f.rule)) for f in audit.audit(vault)
    }


def test_a_well_formed_vault_has_no_findings(tmp_path):
    vault = make_vault(tmp_path, {"decisions/first.md": DECISION})
    assert audit.audit(vault) == []


def test_a_note_without_frontmatter_is_reported(tmp_path):
    vault = make_vault(
        tmp_path, {"decisions/bare.md": "# Bare\n\nPart of [[ember]].\n"}
    )
    assert rules(vault) == {("decisions/bare.md", "frontmatter")}


def test_a_note_missing_a_required_field_is_reported(tmp_path):
    text = DECISION.replace("updated: 2026-10-02\n", "")
    vault = make_vault(tmp_path, {"decisions/first.md": text})
    assert rules(vault) == {("decisions/first.md", "frontmatter")}


def test_a_tag_outside_the_vocabulary_is_reported(tmp_path):
    text = note("decision", ["type/decision", "domain/runtime", "domain/made-up"])
    vault = make_vault(tmp_path, {"decisions/first.md": text})
    assert rules(vault) == {("decisions/first.md", "unknown-tag")}


@pytest.mark.parametrize(
    "tags",
    [
        ["type/decision"],
        ["type/decision", "type/moc", "domain/runtime"],
        ["type/decision", "domain/runtime", "status/draft", "status/stale"],
    ],
    ids=["no-domain", "two-types", "two-statuses"],
)
def test_tag_cardinality_is_enforced(tmp_path, tags):
    vault = make_vault(tmp_path, {"decisions/first.md": note("decision", tags)})
    assert rules(vault) == {("decisions/first.md", "tag-cardinality")}


def test_the_type_tag_must_match_the_type_field(tmp_path):
    text = note("decision", ["type/moc", "domain/runtime"])
    vault = make_vault(tmp_path, {"decisions/first.md": text})
    assert rules(vault) == {("decisions/first.md", "type-mismatch")}


def test_a_wikilink_to_a_missing_note_is_reported(tmp_path):
    body = "Part of [[ember]]; see [[nowhere]]."
    text = note("decision", ["type/decision", "domain/runtime"], body=body)
    vault = make_vault(tmp_path, {"decisions/first.md": text})
    assert rules(vault) == {("decisions/first.md", "broken-wikilink")}


def test_code_refs_resolve_from_the_repository_root(tmp_path):
    (tmp_path / "present.py").write_text("", encoding="utf-8")
    refs = "code-refs:\n  - present.py\n  - missing.py"
    text = note("decision", ["type/decision", "domain/runtime"], extra=refs)
    vault = make_vault(tmp_path, {"decisions/first.md": text})
    assert rules(vault) == {("decisions/first.md", "broken-code-ref")}


def test_a_note_the_hub_cannot_reach_is_an_orphan(tmp_path):
    vault = make_vault(tmp_path, {"decisions/first.md": DECISION}, linked=False)
    assert rules(vault) == {("decisions/first.md", "orphan")}


def test_a_vault_without_its_hub_is_reported(tmp_path):
    vault = make_vault(tmp_path, {})
    (vault / "ember.md").unlink()
    assert rules(vault) == {("ember.md", "missing-hub")}


def test_the_project_vault_passes_the_audit():
    result = subprocess.run(  # noqa: S603 - this interpreter running the repo's script
        [sys.executable, str(SCRIPT), str(ROOT / "vault")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout


def test_the_audit_exits_nonzero_and_names_the_rule(tmp_path):
    vault = make_vault(tmp_path, {"decisions/first.md": DECISION}, linked=False)
    result = subprocess.run(  # noqa: S603 - this interpreter running the repo's script
        [sys.executable, str(SCRIPT), str(vault)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.startswith("orphan: decisions/first.md")
