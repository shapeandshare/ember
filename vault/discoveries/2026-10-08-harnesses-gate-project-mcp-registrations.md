---
title: "Codex and Claude Code silently gate project-scope MCP registrations"
type: discovery
tags:
  - type/discovery
  - domain/cli
  - domain/mcp
  - status/draft
created: "2026-10-08"
updated: "2026-10-08"
code-refs:
  - ember/codex/codex_trust.py
  - ember/codex/codex_config.py
  - ember/claude/claude_config.py
  - ember/cfg/repo_root.py
---

# Codex and Claude Code silently gate project-scope MCP registrations

Part of [[ember]]. A project-scope registration can be on disk and still never load:
Codex ignores an untrusted project's `.codex/config.toml`, and Claude Code holds a project
`.mcp.json` server until the user approves it.

## What was tested

Read upstream source and docs on 2026-10-08: `openai/codex` main at `780d7ab`
(`codex-rs/config/src/project_trust.rs`, `codex-rs/git-utils/src/trust.rs`,
`codex-rs/config/src/mcp_types.rs`) and Claude Code's MCP, settings, and environment
variable docs on code.claude.com. The local Codex CLI 0.147.0 `codex mcp add --help`
confirmed the stdio entry shape.

## Finding

- **Codex trust.** Trust lives in the global `$CODEX_HOME/config.toml` (default
  `~/.codex/config.toml`) as `[projects."<path>"] trust_level = "trusted" | "untrusted"`.
  The lookup keys are the working directory, then its main checkout root (a linked
  worktree maps to its repository), each canonical first and then as spelled. The first
  key present decides, even without a `trust_level`, and matching is by exact key, never
  by prefix. An absent or `untrusted` entry means project `.codex/` layers are skipped.
- **Codex environment.** An MCP child inherits only a whitelist (`HOME`, `PATH`, `SHELL`,
  `USER`, `TMPDIR`, ...). `env` values are literal (no `${VAR}`), so a shell secret must be
  forwarded by name with `env_vars`. Timeout defaults disagree between the docs and the
  code paths.
- **Claude Code scopes.** `claude mcp add` writes user scope to the top-level `mcpServers`
  of `~/.claude.json` (`$CLAUDE_CONFIG_DIR/.claude.json` when set), local scope to
  `projects["<repo root or cwd>"].mcpServers` in the same file, and project scope to
  `.mcp.json`. Its project-key canonicalization is inconsistent across symlinks and
  worktrees.
- **Claude Code approval.** `.mcp.json` servers need approval recorded in settings files
  (`enabledMcpjsonServers`, `disabledMcpjsonServers`, `enableAllProjectMcpServers`), and
  since 2.1.196 repo-committed approvals are ignored in an untrusted workspace.

## Relevance

- `ember init --codex` and `ember doctor` reproduce Codex's lookup and say why a project
  file is ignored ([[2026-10-08-doctor-reports-registration-from-config-files]]).
- Claude Code approval is not emulated; doctor reminds the user and points at
  `claude mcp list`.
- The Codex entry ember writes forwards `EMBER_AUTH_TOKEN` through `env_vars` and pins
  explicit timeouts.

## References

- https://github.com/openai/codex/blob/780d7ab09741241380586b07882c635037a6ba21/codex-rs/config/src/project_trust.rs
- https://code.claude.com/docs/en/mcp
- `ember/codex/codex_trust.py`, `ember/claude/claude_config.py`
