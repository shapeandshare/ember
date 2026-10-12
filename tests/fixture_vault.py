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
    "Anomalies — Domain MOC.md": """---
title: Anomalies
type: moc
tags:
  - type/moc
  - domain/gameplay
created: '2026-01-01'
updated: '2026-01-02'
---

# Anomalies

Map of Content for the anomaly domain.
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

The engine split keeps scene logic in GDScript and simulation in Rust. The
decision settled a long argument about where movement constraints should run,
and it came down to testability: the Rust core can be exercised without
launching the editor, while the scene tier keeps its fast iteration loop.
Everything that crosses the boundary speaks a small message vocabulary that
both sides version together. The split also keeps a hostile editing session
from breaking simulation determinism, which the gameplay tests rely on when
they replay recorded inputs. The compromise cost one indirection layer, and
everyone agreed it was worth it.
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

This note carries a tag that never reached the controlled vocabulary, so the
miner records it as drift and moves on. The tag was coined during a late-night
session and never proposed for the extension log, which is exactly the class
of quiet divergence the audit exists to surface. When the next vocabulary
pass runs, either the tag gets proposed properly or the note gets retagged.
Until then the note is not usable as ground truth, because its intended axis
is ambiguous and any guess would poison the benchmark instead of measuring
it.
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

Generation must order biomes before movement constraints. When the pipeline
ran movement first, spawn smoothing pulled against biome seams and produced
corridors that the traversal probes could not cross, which cost the team a
week of playtest notes. The dependency is now explicit: terrain and biome
assignment settle first, then the movement pass consumes their output. The
note records the failure mode so the next pipeline reshuffle keeps the
ordering, and so the benchmark can test whether an agent reads the constraint
out of the text rather than from the ordering of the code.
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

The deploy log contained AKIAQWERTYUIOPASDF12 verbatim, which is why this
note exists at all. The string was pasted during a debugging session and
nobody rotated it before the incident review, so the note went out as a
warning to the team. The fix was a two-part change: the token was revoked and
replaced with a short-lived credential, and the log-scrubbing step now runs
on every deploy so a credential never lands in a note body again. This note
stays as the record of what happened, and of why the scrubber exists.
""",
    "Narrative/Empty Tags.md": """---
title: Empty Tags
type: reference
tags: []
created: '2026-01-05'
updated: '2026-01-06'
---

# Empty Tags

A note that never earned its tags. It started as a scratch pad during a
design conversation and was promoted to a note by habit, but nobody assigned
a type or domain because the content never settled into a decision or a
discovery. The audit flags it as out of bounds: an empty tag set teaches a
model nothing about the vocabulary, so the miner has to record it and move
on. If the content matures, the note can be retagged and mined like any
other.
""",
    "Narrative/No Header.md": "No frontmatter here, just raw text.\n",
    "legacy.base": "raw artifact\n",
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

Shared terms for playtests and notes. The team kept inventing synonyms for
the same handful of concepts, so this glossary pins one name per idea and
points at the note that owns the definition. Entries cover the pipeline
vocabulary, the movement vocabulary, and the handful of incident terms that
keep resurfacing in session logs. When a note disagrees with the glossary,
the glossary wins until someone updates it deliberately, which keeps
playtest reports comparable across sessions and reviewers.
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

Planned the vocabulary extension work. The session walked the outstanding
drift reports, agreed which tags get proposed at the next pass, and assigned
owners for the notes that need retagging. It also settled the audit cadence:
the mechanical pass runs on every vault audit, and the semantic pass runs
before each spec milestone. The session closed with a checklist of notes to
re-verify, all of which are linked from the extension log so the next
session can pick up without re-reading everything.
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
    "Specs/048 Sibling/048 Sibling - plan.md": """---
title: 048 Sibling - plan
type: plan
tags:
  - type/spec
created: '2026-01-07'
updated: '2026-01-08'
---

# 048 Sibling - plan

Sibling artifact whose field and tag disagree.
""",
    "Specs/049 Drifted/049 Drifted - data-model.md": """---
title: 049 Drifted - data-model
type: data-model
tags:
  - type/reference
created: '2026-01-07'
updated: '2026-01-08'
---

# 049 Drifted - data-model

A sibling whose only tag is a governed reference type. The data-model
artifact describes the entities and relationships of the spec, and this
fixture copy is long enough to clear the word floor so that only the Specs
path rule can keep it out of the candidate pool, exactly like the real
vault's remaining sibling artifacts. It exists to pin the rule: anything
under the Specs tree is out of scope for the mined recipes, whatever its
frontmatter claims, because these files are workflow artifacts rather than
the memory notes the benchmark grades. The miner records it with the
out_of_scope reason and moves on.
""",
    "_meta/tags.md": TAGS_MD,
}

BINARY_FILES: Final[dict[str, bytes]] = {
    "Art/panel.png": b"\x89PNG\r\n\x1a\nfixture-bytes",
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
    for relative, data in BINARY_FILES.items():
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    oversized = vault / "Narrative" / "Too Long.md"
    oversized.write_text(
        "---\ntitle: Too Long\ntype: reference\ntags:\n  - type/reference\n"
        "created: '2026-01-05'\nupdated: '2026-01-06'\n---\n\n# Too Long\n\n"
        + "word "
        * 12010,
        encoding="utf-8",
    )
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
