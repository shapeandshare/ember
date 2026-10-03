---
title: Adopt a governed project vault like the sibling repositories
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/tooling
  - status/draft
created: 2026-10-02
updated: 2026-10-02
code-refs:
  - .opencode/opencode.json
  - scripts/vault_audit.py
  - shared/vault.mk
  - .opencode/commands/vault-health.md
---

# Adopt a governed project vault like the sibling repositories

Part of [[ember]]. ember now keeps an Obsidian vault at `vault/` for the memory of its
own development, as anvil, darkharbour, and wellspring do.

## Context

The sibling repositories keep decisions, discoveries, and session logs in an Obsidian
vault, served to agents by the `vault` MCP server (`@bitbonsai/mcpvault`). ember had no
such place: this knowledge lived only in commit messages and chat sessions.

## Decision

- Follow wellspring, the closest match in size: lowercase folders (`decisions/`,
  `discoveries/`, `sessions/`), dated file names, the hub [[ember]], the controlled
  [[tags|tag vocabulary]], and templates in `vault/_meta/templates/`.
- Pin `@bitbonsai/mcpvault@0.12.4`, the version darkharbour and wellspring run.
- Register the server in `.opencode/opencode.json` rather than the root
  `opencode.json`, which `ember init` rewrites with per-machine paths. opencode merges
  the two; see [[2026-10-02-opencode-merges-the-dot-opencode-config]].
- Check vault health with `make vault-audit`, and audit the real vault in the unit
  suite so that `make check` and CI catch broken notes.
- Constitution Article IX and the AGENTS.md vault protocol hold the rules.

## Consequences

- Launch opencode from the repository root. The server resolves `vault` against the
  directory opencode starts in.
- Agent-written notes start at `status/draft`. Only a human sets `status/canonical`.
