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

For now, install it locally with the `ember` CLI (recommended):

```bash
ember init --opencode            # project scope
ember init --opencode --global   # all projects
```

That writes a generated plugin to `.opencode/plugins/ember.js` (or
`~/.config/opencode/plugins/ember.js`) with the absolute command path baked in,
and installs the `ember-advise` skill next to it.

To use this package as an npm dependency instead, add it to your opencode config:

```json
{ "plugin": ["opencode-ember-advise"] }
```

It resolves `ember-mcp` at every launch; set `EMBER_MCP` to override the path.
