---
title: "ember doctor reports agent registration from config files, never harness CLIs"
type: decision
tags:
  - type/decision
  - domain/cli
  - status/draft
created: "2026-10-08"
updated: "2026-10-08"
code-refs:
  - ember/commands/registration.py
  - ember/commands/doctor.py
  - ember/commands/agents.py
---

# ember doctor reports agent registration from config files, never harness CLIs

Part of [[ember]]. `ember doctor` now ends with, for each harness, the binary on `PATH`
and where ember is registered, read from that harness's own config files.

## Context

Clients onboarding across opencode, Kilo Code, Codex CLI, and Claude Code had no single
answer to "did it work?". Each harness has its own config format and list command, and
two of them can ignore a registration that is on disk
([[2026-10-08-harnesses-gate-project-mcp-registrations]]). Constitution Article IV
forbids interfering with a running host, and the test suite never invokes agent CLIs.

## Decision

- Read config files only (opencode and Kilo JSON, Codex TOML, `~/.claude.json`,
  `.mcp.json`). Never run `opencode`, `codex`, `claude`, or `git`. A malformed file
  counts as "not registered", never as an error.
- Registration lines are `[info]` and never change doctor's exit code: a user may use only
  one harness.
- Emulate a harness's gate only when it is a documented, single-file, exact rule. Codex
  project trust is mirrored exactly (`ember/codex/codex_trust.py`); Claude Code's
  `.mcp.json` approval is multi-file and trust-gated, so doctor notes it and points at
  `claude mcp list`.
- `ember init --codex` reuses the same trust check to say whether the project file will
  load.
- Rejected for now: defaulting `--codex` to global scope (inconsistent with the other
  harnesses; precise trust reporting removes the silent failure instead), an `--all` flag,
  and a project-scope `uninit`. Revisit when clients ask.

## Consequences

- A new harness integration ships a read-only `has_entry()` next to its writer and a pair
  of lines in `registration_lines()`.
- If Codex changes its trust lookup, update `codex_trust.py` and its tests together.
