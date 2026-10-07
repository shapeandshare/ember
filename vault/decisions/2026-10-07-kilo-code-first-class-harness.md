---
title: "Adopt Kilo Code as a first-class supported harness"
type: decision
tags:
  - type/decision
  - domain/agent-kit
  - domain/cli
  - status/draft
created: "2026-10-07"
updated: "2026-10-07"
code-refs:
  - ember/agent_kit/api.py
  - ember/agent_kit/instructions.md
  - ember/agent_kit/ember-advise/SKILL.md
  - ember/kilocode/kilocode_config.py
  - ember/commands/agents.py
  - ember/commands/parser.py
  - ember/commands/doctor.py
  - ember/mcp/mcp_server.py
---

# Adopt Kilo Code as a first-class supported harness

Part of [[ember]]. Kilo Code joins opencode, Claude Code, and Codex CLI as a
first-class onboarding target in the agent kit.

## Context

ember's agent onboarding kit (`ember/agent_kit/`) previously named opencode, Claude
Code, and (partially) Codex CLI as supported harnesses. There was no Kilo Code
support and no prior evidence of demand in the repo.

Consulted `ember_advise` before committing effort (constitution Article VII,
"dogfood"). With no stated requirement, the model recommended deferring
(`should_prioritize_now` P(true) = 0.029, `recommended_path` = `defer_no_action`,
confidence 0.72) — the generic MCP server already works with any MCP client
without kit changes, and YAGNI argues against speculative onboarding work.

The user then stated explicitly: "our primary audience will use kilocode and we
must support this as a first class harness." Re-running the same check with that
fact included flipped the read entirely: `should_prioritize_now` P(true) = 0.982,
`recommended_path` = `research_first` (confirm Kilo Code's actual skill/MCP
conventions before writing code), confidence 0.951.

Research step: Kilo Code (the `kilo-config` skill reference, and this
project's own Kilo Code session environment) confirmed:
- Skills load from `{skill,skills}/<name>/SKILL.md` inside `.kilo/` (or legacy
  `.kilocode/`), both project-local and global (`~/.config/kilo/`, `~/.kilo/`).
- MCP servers register in `kilo.json` under `"mcp"`, with the identical entry
  shape ember already uses for opencode (`type: "local"`, `command`, `enabled`,
  `timeout`, `environment`).
- `AGENTS.md` is read automatically, same as opencode and Claude Code.

## Decision

Add `kilocode` as a fully supported agent in the onboarding kit:

- `ember/agent_kit/api.py`: added `"kilocode": (".kilo/skills", ".config/kilo/skills")`
  to `_SKILL_ROOTS`. This is the single generic extension point; `AGENTS`,
  `skill_path`, `install_skill`, the CLI's `--agent` choices, and `uninstall`'s
  global-skill cleanup loop all picked it up automatically.
- Added `ember/kilocode/kilocode_config.py`, mirroring
  `ember/opencode/opencode_config.py`'s `write`/`remove`/path-validation
  functions but targeting `kilo.json`. It imports and reuses
  `opencode_config.build_entry` directly, since the MCP entry shape is
  identical — no duplicated entry-building logic.
- Added `--kilocode` to `ember init`, parallel to `--opencode`: writes the
  `mcp.ember` entry to `kilo.json` and installs the skill, in one step.
- `ember uninstall` now also removes the global `kilo.json` entry.
- Did not add a Kilo Code equivalent of the opencode JS plugin
  (`opencode_plugin.py`). The plain `kilo.json` write already persists across
  restarts without needing a config-injecting plugin hook; adding one would be
  unverified extra surface for no confirmed need (YAGNI).
- A follow-up critical review caught the live agent-facing text: the MCP
  `initialize.instructions` (`ember/agent_kit/instructions.md`, ≤ 2048 bytes)
  and the `ember-advise` `SKILL.md` playbook both still said only `(opencode:
  ember_advise)`, which is what any connecting agent — including Kilo Code —
  actually reads at runtime. Fixed both to `(opencode/Kilo Code: ember_advise)`,
  within the 2 KB cap (1978 of 2048 bytes used). Also fixed the module
  docstring in `ember/mcp/mcp_server.py` (tool-namespacing explanation named
  opencode only) and added a `kilo` binary check to `ember doctor` alongside
  the existing `opencode` check, for diagnostic parity.

## Consequences

- Kilo Code is documented in README's agent-onboarding table and CLI reference,
  and listed in AGENTS.md alongside opencode and Claude Code.
- `tests/test_agent_kit.py`, `tests/test_cli.py`, and the new
  `tests/test_kilocode_config.py` pin this contract (Article XI: tests shipped
  with the code, TDD red-before-green followed for the `_SKILL_ROOTS` entry and
  the CLI flag).
- Any future change to the agent kit's public contract (tool name, skill name,
  instructions text) must keep Kilo Code in the same loop as opencode and Claude
  Code per the kit rules in `AGENTS.md`.
- If Kilo Code's own skill- or MCP-loading convention changes upstream, this
  note and `kilocode_config.py` need re-verification — the convention was
  confirmed from the `kilo-config` skill reference, not from Kilo Code's own
  source.
