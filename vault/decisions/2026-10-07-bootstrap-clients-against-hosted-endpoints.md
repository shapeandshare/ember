---
title: "Let ember init bootstrap clients against a hosted endpoint, never writing the token"
type: decision
tags:
  - type/decision
  - domain/agent-kit
  - domain/cli
  - domain/opencode
  - status/draft
created: "2026-10-07"
updated: "2026-10-07"
code-refs:
  - ember/opencode/opencode_config.py
  - ember/opencode/opencode_plugin.py
  - ember/kilocode/kilocode_config.py
  - ember/commands/agents.py
  - ember/commands/parser.py
---

# Let ember init bootstrap clients against a hosted endpoint, never writing the token

Part of [[ember]]. `ember init --server-url <url> [--auth-header <name>]` now
generates a remote `mcp.ember` entry directly, instead of requiring a hand
edit of the generated `opencode.json`/`kilo.json`.

## Context

Remote inference was already fully supported on the client side (`EMBER_SERVER_URL`,
`EMBER_AUTH_TOKEN`, `EMBER_AUTH_HEADER`, `EMBER_ALLOW_INSECURE_TRANSPORT`, resolved
through `cfg/endpoint.py`). But `ember init`'s generated config always wrote a
local-loopback `mcp.ember` entry (`opencode_config.build_entry`) with no way to
target a remote endpoint — the only documented path was hand-editing the JSON
after the fact.

The user asked for bootstrap support for a hosted/remote environment. Consulted
`ember_advise` on scope and the security tradeoff before implementing (dogfood,
Article VII):

- `should_build_cli_support` P(true) = 0.60 — moderately justified, consistent
  with an explicit ask.
- `best_design` → `design_b_omit_token` (P=0.54, `design_c_separate_path` a
  close second at P=0.40): add flags, but never write the raw secret into the
  config file.
- `token_in_config_file_acceptable` P(true) = **0.02** — strongly no. Writing a
  credential into `kilo.json`/`opencode.json` (files that may be project-local
  and committed to version control) is not acceptable.

## Decision

- `opencode_config.build_entry(host, port, autostart, server_url=None,
  auth_header=None)`: when `server_url` is given it replaces the local
  `http://{host}:{port}` URL; `auth_header` is recorded as `EMBER_AUTH_HEADER`
  only alongside a `server_url`. Neither parameter can embed a token — there
  is no token parameter at all.
- `opencode_config.write` and `kilocode_config.write` gained the same two
  optional parameters and forward them to `build_entry`.
- `opencode_plugin.render`/`install` gained an `auth_header` parameter for
  parity, so `ember init --opencode --server-url ...` also bootstraps the
  generated JS plugin correctly (its `EMBER_SERVER_URL` is no longer
  hardcoded to the loopback URL).
- `ember init` gained `--server-url` (reusing the existing
  `add_endpoint_flag` helper already used by `ember status`) and
  `--auth-header`. When `--server-url` is given, `EMBER_AUTOSTART` is forced
  to `"0"` regardless of `--no-autostart` — there is nothing local to
  autostart against a remote endpoint.
- The CLI prints a reminder to export `EMBER_AUTH_TOKEN` in the shell, rather
  than silently doing nothing about the credential.
- Without `--server-url`, `ember init` is unchanged — fully backward
  compatible; all new parameters are optional with `None` defaults.

## Consequences

- `ember init --kilocode --opencode --server-url https://... --auth-header
  X-API-KEY` is now a single command that correctly configures both
  `kilo.json` and `opencode.json` (and the opencode plugin) for a hosted
  endpoint, with zero secrets written to disk.
- Manually verified end-to-end: generated `kilo.json`, `opencode.json`, and
  `.opencode/plugins/ember.js` all contain `EMBER_SERVER_URL`/
  `EMBER_AUTH_HEADER` but grep for "token" across all three files returns
  nothing.
- `tests/test_opencode_config.py`, `tests/test_kilocode_config.py`,
  `tests/test_opencode_plugin.py`, and `tests/test_cli.py` pin this contract,
  including an explicit "never embeds a token" assertion in each config
  writer's test file (Article XI: TDD red-before-green followed throughout).
- `make test` (365 tests, including model-backed) and `make pr-ready` both
  pass after this change.
- Any future flag or config surface that could carry a credential should be
  reviewed against the same P=0.02 "not acceptable" finding before writing it
  to a file ember generates.
