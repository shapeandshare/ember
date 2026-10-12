"""A throwaway vault repository the mined-recipe tests build against.

The real source is the sibling Old Growth checkout; tests must never read it
(Article IV). ``build_fixture_vault`` writes a small governed vault, commits
it, and returns the repository root, the commit, and the vault directory.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

GRANT_TEXT: Final = """**Fixture** © 2026. All rights reserved.

## Exception — ember benchmark reproduction

Notes under `docs/vault/` may be reproduced, transformed, and distributed
within the ember benchmark dataset, with attribution.
"""

TAGS_MD: Final = """---
title: Tag Vocabulary
type: reference
tags:
  - type/reference
created: '2026-01-01'
updated: '2026-01-02'
---

# Tag Vocabulary

> **Extension**: 2026-02-01 — renamed `status/in-progress` to `status/wip`.

The controlled tag vocabulary for the fixture vault.

## `type/*` — Note Type (REQUIRED, singular)

- `type/decision` — Architectural or design decision made by an agent during a session.
- `type/discovery` — Non-obvious constraint, gap, or conflict found by an agent.
- `type/session-log` — Session activity log; permanent audit trail.
- `type/moc` — Map of Content at any of three tiers.
- `type/reference` — Glossary, decision log, open questions.
- `type/spec` — Spec document under `Specs/`.

## `domain/*` — Domain (0 or more)

- `domain/gameplay` — Gameplay systems and mechanics.
- `domain/tooling` — Build, CI, and dev-time tools.

## `status/*` — Note State (0 or 1; omit if stable)

- `status/draft` — Authoring in progress, not yet verified.
- `status/stale` — Known out of date.

## `layer/*` — Implementation Layer (0 or 1)

- `layer/rust-core` — Engine-agnostic Rust core.

## `concept/*` — Cross-Cutting Thread (0 or more)

- `concept/movement` — Movement-related cross-system behavior.
"""

NOTES: Final[dict[str, str]] = {
    "index.md": """---
title: Vault Index
type: reference
tags:
  - type/reference
created: '2026-01-01'
updated: '2026-01-02'
---

# Vault Index

Navigation hub.
""",
    "README.md": """---
title: Vault README
type: reference
tags:
  - type/reference
created: '2026-01-01'
updated: '2026-01-02'
---

# Vault README

How to use the fixture vault.
""",
    "Audio.md": """---
title: Audio
type: moc
tags:
  - type/moc
  - domain/gameplay
created: '2026-01-01'
updated: '2026-01-02'
---

# Audio

Map of Content for the audio domain.
""",
    "Decisions/Rust-GDScript Split Architecture.md": """---
title: Rust-GDScript Split Architecture
type: decision
tags:
  - type/decision
  - domain/tooling
  - layer/rust-core
created: '2026-01-03'
updated: '2026-01-04'
aliases: ["Rust-GDScript Split Architecture"]
system: tooling
code-refs: ["src/x.rs"]
---

# Rust-GDScript Split Architecture

The engine split keeps scene logic in GDScript and simulation in Rust.
""",
    "Decisions/Drifted Tags.md": """---
title: Drifted Tags
type: decision
tags:
  - type/ad-hoc
  - domain/tooling
created: '2026-01-03'
updated: '2026-01-04'
---

# Drifted Tags

This note carries a tag that never reached the controlled vocabulary.
""",
    "Discoveries/Generation Pipeline Order.md": """---
title: Generation Pipeline Order
type: discovery
tags:
  - type/discovery
  - domain/gameplay
  - concept/movement
created: '2026-01-05'
updated: '2026-01-06'
---

# Generation Pipeline Order

Generation must order biomes before movement constraints.
""",
    "Discoveries/A Secret Was Left Here.md": """---
title: A Secret Was Left Here
type: discovery
tags:
  - type/discovery
  - domain/tooling
created: '2026-01-05'
updated: '2026-01-06'
---

# A Secret Was Left Here

The deploy log contained AKIAQWERTYUIOPASDF12 verbatim.
""",
    "Narrative/Empty Tags.md": """---
title: Empty Tags
type: reference
tags: []
created: '2026-01-05'
updated: '2026-01-06'
---

# Empty Tags

A note that never earned its tags.
""",
    "Reference/Glossary.md": """---
title: Glossary
type: reference
tags:
  - type/reference
  - domain/gameplay
created: '2026-01-05'
updated: '2026-01-06'
---

# Glossary

Shared terms for playtests and notes.
""",
    "Sessions/Spec 080 Planning Session.md": """---
title: Spec 080 Planning Session
type: session-log
tags:
  - type/session-log
  - domain/tooling
created: '2026-01-07'
updated: '2026-01-08'
---

# Spec 080 Planning Session

Planned the vocabulary extension work.
""",
    "Specs/047 Car Radio/047 Car Radio.md": """---
title: "047 Car Radio"
type: spec
tags:
  - type/spec
  - domain/gameplay
created: '2026-01-07'
updated: '2026-01-08'
---

# 047 Car Radio

The radio spec.
""",
    "_meta/tags.md": TAGS_MD,
}


@dataclass(frozen=True, slots=True)
class FixtureVault:
    """The fixture repository, its commit, and its vault directory."""

    root: Path
    commit: str
    vault: Path


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed git argv
        ["git", "-C", str(root), *args],  # noqa: S607 - system git by design
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build_fixture_vault(tmp_path: Path) -> FixtureVault:
    """Create the committed fixture vault under ``tmp_path``.

    Parameters
    ----------
    tmp_path : Path
        The pytest temporary directory.

    Returns
    -------
    FixtureVault
        The repository root, the fixture commit, and ``docs/vault``.
    """
    root = tmp_path / "oldgrowth-fixture"
    vault = root / "docs" / "vault"
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "user.name", "Fixture")
    (root / "LICENSES.md").write_text(GRANT_TEXT, encoding="utf-8")
    for relative, text in NOTES.items():
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(
        root,
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--no-verify",
        "-q",
        "-m",
        "fixture vault",
    )
    commit = _git(root, "rev-parse", "HEAD")
    return FixtureVault(root=root, commit=commit, vault=vault)


def commit_change(root: Path, relative: str, text: str) -> str:
    """Write ``relative`` under ``root``, commit it, and return the new commit."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(root, "add", "--", relative)
    _git(
        root,
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--no-verify",
        "-q",
        "-m",
        f"update {relative}",
    )
    return _git(root, "rev-parse", "HEAD")
