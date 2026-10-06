# Changelog — opencode plugin (`opencode-ember-advise`)

All notable changes to the opencode plugin package are documented here.
Versions follow [Semantic Versioning](https://semver.org/); changes follow
[Conventional Commits](https://www.conventionalcommits.org/) with scope `plugin`.

<!-- next-version -->
## plugin/v0.4.0 (2026-10-06)

### Feat

- feat(ember): support remote inference servers (#70)

## plugin/v0.3.2 (2026-10-05)

### Fix

- fix(ember): enforce trust boundaries — loopback URL, media kwargs allowlist, EMBER_MCP validation (#58)

## plugin/v0.3.1 (2026-10-05)

### Fix

- fix(plugin): respect EMBER_AUTOSTART from the environment (#48)

### Miscellaneous

- docs(plugin): document the standalone versioning policy (#47)

## plugin/v0.3.0 (2026-10-04)

### feat

- feat: test both release paths end-to-end (#40)

## plugin/v0.2.0 (2026-10-04)

### feat

- feat(plugin): add clef and advise to npm keywords (#37)
- feat(plugin): add version history link to README (#33)
- chore: add per-component versioning and commit scope discipline (#31)
- docs: retitle the brand assets for ember
- refactor!: rename the opencode plugin package to opencode-ember-advise
- feat: rebrand the opencode plugin package as opencode-gut-feeling
- Relicense under MIT
- Add publishable opencode plugin package


## plugin/v0.1.0 (2026-10-02)

### feat

- initial opencode plugin: registers the local ember MCP server (`advise` tool) with opencode
- resolves `ember-mcp` from `EMBER_MCP`, uv-tool bin dir, or Homebrew candidates
- passes explicit `PATH` so opencode launched from a GUI finds the binary
