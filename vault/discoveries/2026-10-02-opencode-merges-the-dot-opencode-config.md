---
title: opencode merges .opencode/opencode.json with the root opencode.json
type: discovery
tags:
  - type/discovery
  - domain/opencode
  - domain/tooling
  - status/draft
created: 2026-10-02
updated: 2026-10-02
code-refs:
  - .opencode/opencode.json
  - ember/opencode_config.py
---

# opencode merges .opencode/opencode.json with the root opencode.json

Part of [[ember]]. opencode loads an `opencode.json` inside `.opencode/` and merges it
with the project's root `opencode.json`, although the config docs only mention agents,
commands, and plugins for `.opencode` directories. It also starts local MCP servers in
the directory it was launched from.

## What was tested

With opencode `0.0.0-dev-202610022056`, in scratch git repositories:

- `.opencode/opencode.json` defined a `vault` MCP server and the root `opencode.json`
  defined `ember`. `opencode mcp list` showed both connected.
- A server command that wrote its working directory to a file, launched from a
  subdirectory, recorded that subdirectory rather than the repository root.

## Finding

- Both config files load, and their `mcp` entries merge.
- A relative path in an MCP command, such as mcpvault's `vault` argument, resolves
  against the launch directory. From a subdirectory the server still reports
  "connected" but serves a folder that doesn't exist.

## Relevance

- Shared settings go in the tracked `.opencode/opencode.json`. The root
  `opencode.json` stays per-machine and gitignored, because `ember init` writes this
  checkout's absolute paths into it.
- Launch opencode from the repository root so the `vault` server finds `vault/`.

## References

- `ember/opencode_config.py` (what `ember init` writes)
- https://opencode.ai/docs/config (config precedence)
