---
title: "ember init leaked the repo's vault MCP server into client configs"
type: discovery
tags:
  - type/discovery
  - domain/opencode
  - domain/cli
  - status/draft
created: "2026-10-08"
updated: "2026-10-08"
code-refs:
  - ember/opencode/opencode_config.py
  - ember/commands/registration.py
  - .opencode/opencode.json
---

# ember init leaked the repo's vault MCP server into client configs

Part of [[ember]]. `opencode_config.write()` merged an `mcp.vault` entry
(`npx -y @bitbonsai/mcpvault@0.12.4 vault`) into every opencode config it wrote, which
contradicts [[2026-10-02-adopt-a-governed-project-vault]]: that decision put the vault
server only in the committed `.opencode/opencode.json`.

## What was tested

- A red test ran `ember init --opencode --global` with a sandboxed HOME: the global
  `~/.config/opencode/opencode.json` came back with both `mcp.ember` and `mcp.vault`.
- `.opencode/opencode.json` already registers the identical vault entry, so the merge was
  redundant for contributors.

## Finding

- Every client who ran `ember init` got an unrelated vault server in that project's
  `opencode.json`. With `--global`, every project they open starts it: an `npx` fetch and
  a server for a `vault/` folder most projects don't have.
- The repo's own workflow never needed it, because opencode merges
  `.opencode/opencode.json` with the root file
  ([[2026-10-02-opencode-merges-the-dot-opencode-config]]).

## Relevance

- `write()` now registers only ember and never deletes a vault entry it finds: an
  identical entry may be the user's own (sibling repositories run the same pin).
- `ember doctor` reports an exact copy of the legacy entry in the global opencode config
  (the `opencode legacy` line) so affected users can remove it themselves.
- Guarded by `test_write_does_not_register_the_vault_server` and
  `test_init_registers_only_ember_never_the_repo_vault_server`.

## References

- `ember/opencode/opencode_config.py` (`write`, `has_legacy_vault_entry`)
- `ember/commands/registration.py` (`registration_lines`)
