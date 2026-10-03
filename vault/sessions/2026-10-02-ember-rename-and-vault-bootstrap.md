---
title: Rename gut-feeling to ember and bootstrap the vault
type: session-log
tags:
  - type/session-log
  - domain/governance
  - domain/tooling
created: 2026-10-02
updated: 2026-10-02
---

# Rename gut-feeling to ember and bootstrap the vault

Part of [[ember]]. One session renamed the product to match its mascot, published the
rename, and set up this vault.

## What happened

- Renamed every product identifier from gut-feeling to ember. The "gut feeling" flavor
  text, the `gut` alias, history entries, and saved prompts kept their wording.
- A second pass found that `opencode-ember` is taken on npm, and renamed the plugin
  package to `opencode-ember-advise`.
- Switched the distribution to `gut`, renamed the GitHub repository to
  `shapeandshare/ember`, and removed the README title above the banner.
- Pushed ten commits to `main` (`e4bfcf3..bc0c500`). CI passed, and the README install
  command worked from GitHub.
- Added this vault, following wellspring: the hub, tag vocabulary, templates,
  `scripts/vault_audit.py`, `make vault-audit`, the `/vault-health` command, the
  `vault` MCP server, the AGENTS.md vault protocol, and constitution Article IX.

## Decisions and discoveries written back

- [[2026-10-02-rename-the-product-to-ember]]
- [[2026-10-02-publish-as-gut-and-opencode-ember-advise]]
- [[2026-10-02-adopt-a-governed-project-vault]]
- [[2026-10-02-ember-names-are-taken-on-pypi-and-npm]]
- [[2026-10-02-opencode-merges-the-dot-opencode-config]]

## Follow-ups

- The local checkout folder is still named `gut-feeling`.
- Git hooks are not enabled in this checkout; `make setup-hooks` enables them.
