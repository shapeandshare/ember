---
title: Tag vocabulary
type: reference
tags:
  - type/reference
  - domain/governance
created: 2026-10-02
updated: 2026-10-05
---

# Tag vocabulary

Every tag in a vault note must come from this list (constitution Article IX). Add
a tag here before you use it. Each note carries exactly one `type/*` tag, at least
one `domain/*` tag, and at most one `status/*` tag; drop `status/*` once a note is
stable. The `type/*` tag matches the note's `type` field.

## `type/*`: note type (exactly one)

| Tag | Applies to |
| --- | --- |
| `type/decision` | A decision made during a session, with context and consequences |
| `type/discovery` | A non-obvious constraint, gap, or conflict |
| `type/session-log` | What a session did (append-only) |
| `type/reference` | Glossaries, vocabularies, open questions, external pointers |
| `type/moc` | Maps of content, such as the hub |

## `status/*`: note state (zero or one)

| Tag | Meaning |
| --- | --- |
| `status/draft` | Written, not yet verified against the codebase |
| `status/reviewed` | Verified against the codebase |
| `status/stale` | Known to be out of date |
| `status/superseded` | Replaced by another note, which it links |
| `status/canonical` | Fully authoritative; set by a human only |

## `domain/*`: what the note is about (one or more)

| Tag | Covers |
| --- | --- |
| `domain/governance` | Constitution, policies, naming, and the vault itself |
| `domain/runtime` | Model loading on MPS or CPU, the engine, numerics (`ember/serving/runtime.py`) |
| `domain/server` | The HTTP model server and its lifecycle (`ember/serving/server.py`, `ember/serving/process.py`) |
| `domain/mcp` | The MCP server and the `advise` tool contract (`ember/mcp/mcp_server.py`) |
| `domain/agent-kit` | Instructions, the `ember-advise` skill, the AGENTS.md snippet, thresholds |
| `domain/cli` | The `ember` and `gut` commands (`ember/cli.py`) |
| `domain/opencode` | opencode config, the generated plugin, the npm plugin package |
| `domain/models` | The pinned model registry, downloads, the Hugging Face cache |
| `domain/brand` | The Ember mascot, banners, palette, and other brand assets |
| `domain/provenance` | `provenance.json`, licensing evidence, and pins |
| `domain/tooling` | Makefile, CI, hooks, uv, ruff, mypy, bandit, spec-kit |
