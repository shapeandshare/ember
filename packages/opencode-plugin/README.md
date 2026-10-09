# opencode-ember-advise

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img src="assets/hero-light.svg" alt="ember — Ember hugs its glowing tummy. Give your agent a gut feeling." width="1200">
</picture>

An [opencode](https://opencode.ai) plugin that registers the locally installed
ember MCP server (`ember-mcp`) with opencode, so agents gain the
`ember_advise` tool.

Register-only and lazy: it injects the `mcp.ember` entry on every launch; the
model server itself starts on the first tool call.

## Install

Install it with the `ember` CLI:

```bash
ember init --opencode            # project scope
ember init --opencode --global   # all projects
```

That writes a generated plugin to `.opencode/plugins/ember.js` (or
`~/.config/opencode/plugins/ember.js`) with the absolute command path baked in,
and installs the `ember-advise` skill next to it.

This package is not published to npm, so `{ "plugin": ["opencode-ember-advise"] }`
does not install it. The source here resolves `ember-mcp` at every launch (set
`EMBER_MCP` to override the path) and stays tested in CI.

## Versioning

Separate releases stopped after `plugin/v0.4.0`, and `package.json` keeps that
version. Later changes appear in the root [CHANGELOG.md](../../CHANGELOG.md);
[CHANGELOG.md](CHANGELOG.md) keeps the history up to `plugin/v0.4.0`.
