# opencode-clever

An [opencode](https://opencode.ai) plugin that registers the locally-installed
Clef decision-model MCP server (`clef-mcp`) with opencode.

Register-only and lazy: it injects the `mcp.clef` entry on every launch; the
model server itself starts on the first tool call.

## Install

For now, install it locally with the `clef` CLI (recommended):

```bash
clef init --opencode            # project scope
clef init --opencode --global   # all projects
```

That writes a generated plugin into `.opencode/plugins/clef.js` (or
`~/.config/opencode/plugins/clef.js`) with the absolute command path baked in.

To use this package as an npm dependency instead, add it to your opencode config:

```json
{ "plugin": ["opencode-clever"] }
```

Set `CLEF_MCP` to override the `clef-mcp` path.
