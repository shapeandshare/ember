---
title: "Client MCP registration hygiene"
type: session-log
tags:
  - type/session-log
  - domain/cli
  - domain/opencode
created: "2026-10-08"
updated: "2026-10-08"
---

# Client MCP registration hygiene

Part of [[ember]]. After reviewing how clients register ember across harnesses, fix what
`ember init` writes and make `ember doctor` show where ember is registered.

## What happened

- Verified the uncommitted Codex CLI support from
  [[2026-10-08-codex-review-and-s3-rename]] and researched Codex and Claude Code
  registration upstream.
- Red first: `ember init` stopped merging `mcp.vault` into generated opencode configs;
  existing vault entries are left alone.
- Added read-only detection: `has_entry()` for the opencode, Kilo, and Codex configs,
  `has_legacy_vault_entry()`, `ember/cfg/repo_root.py` (checkout and main-worktree roots
  from `.git`), `ember/codex/codex_trust.py` (Codex's trust lookup), and
  `ember/claude/claude_config.py` (user, local, and project scopes).
- `ember/commands/registration.py` feeds `ember doctor`, and `ember init --codex` reports
  the project's trust state precisely.
- The test sandbox now clears `CODEX_HOME` and `CLAUDE_CONFIG_DIR`, so global-path tests
  cannot reach the host's real config.
- README gained a "Check what's registered" table; AGENTS.md was updated.
- Critical review before the PR found, and red-first tests now pin:
  - opencode and Kilo `write()` replaced any config they could not parse (an
    `opencode.json` with comments, say) with a fresh file, silently dropping the user's
    settings. Both now refuse, through a shared `load_config_for_merge()`, and `remove()`
    no longer crashes on a config without an `mcp` table.
  - A refused write surfaced as a Python traceback; `ember init` now reports it as
    `error: ...` and exits 1.
  - `kilo.json`, `.codex/config.toml`, and the Kilo/Codex/Claude Code `ember-advise` skill
    copies that `ember init` and `ember agents install` write into a checkout were not
    gitignored.
  - Code comments still named a private sibling repository after the deployment docs had
    been scrubbed of internal names; they now describe the pattern instead.

## Decisions and discoveries written back

- [[2026-10-08-doctor-reports-registration-from-config-files]]
- [[2026-10-08-ember-init-leaked-the-vault-server]]
- [[2026-10-08-harnesses-gate-project-mcp-registrations]]

## Follow-ups

- Deferred: `ember init --all`, a project-scope `ember uninit`, and writing Claude Code's
  config (users run `claude mcp add`).
