# opencode-gut-feeling

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img src="assets/hero-light.svg" alt="gut-feeling — Ember hugs its glowing tummy. Give your agent a gut feeling." width="1200">
</picture>

An [opencode](https://opencode.ai) plugin that registers the locally installed
gut-feeling MCP server (`gut-feeling-mcp`) with opencode, so agents gain the
`gut-feeling_advise` tool.

Register-only and lazy: it injects the `mcp.gut-feeling` entry on every launch; the
model server itself starts on the first tool call.

## Install

For now, install it locally with the `gut-feeling` CLI (recommended):

```bash
gut-feeling init --opencode            # project scope
gut-feeling init --opencode --global   # all projects
```

That writes a generated plugin to `.opencode/plugins/gut-feeling.js` (or
`~/.config/opencode/plugins/gut-feeling.js`) with the absolute command path baked in,
and installs the `gut-feeling-advise` skill next to it.

To use this package as an npm dependency instead, add it to your opencode config:

```json
{ "plugin": ["opencode-gut-feeling"] }
```

It resolves `gut-feeling-mcp` at every launch; set `GUT_FEELING_MCP` to override the path.
