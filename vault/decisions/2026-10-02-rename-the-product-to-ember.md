---
title: Rename the product to ember to match the mascot
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/brand
  - status/draft
created: 2026-10-02
updated: 2026-10-02
code-refs:
  - pyproject.toml
  - ember/agent_kit/instructions.md
  - .specify/memory/constitution.md
---

# Rename the product to ember to match the mascot

Part of [[ember]]. The product formerly called gut-feeling is now ember, the name of
its primary mascot. The "gut feeling" phrasing stays as flavor text.

## Context

Ember was already the primary mascot (`assets/brand/README.md`). The owner wanted the
product name to match it, while keeping the tagline *Give your agent a gut feeling.*
and the rest of the gut-feeling flavor.

## Decision

- Every product identifier moved to ember: the Python package, the `ember` command,
  the MCP server and its `ember_advise` tool, the `ember-advise` skill,
  `ember://guide`, the `EMBER_*` settings, the app directory, the `--ember-*` CSS
  tokens, and the GitHub repository (`shapeandshare/ember`).
- The `gut` command alias stays, as flavor and as a fallback name.
- "Gut feeling" phrasing is flavor text, not a name: the tagline, "a local gut feeling
  for coding agents", and the heading of the AGENTS.md snippet. AGENTS.md and the
  constitution now say so.
- History entries, saved image prompts, and dated provenance checks keep the old name.

## Consequences

- Package registries forced two exceptions; see
  [[2026-10-02-publish-as-gut-and-opencode-ember-advise]].
- Brand asset edits refreshed their hashes in `provenance.json`.
- Per-machine files written by the old `gut-feeling init` stop working; regenerate them
  with `make init` or `make opencode`.
