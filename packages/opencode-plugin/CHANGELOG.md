# Changelog — opencode plugin (`opencode-ember-advise`)

All notable changes to the opencode plugin package are documented here.
Versions follow [Semantic Versioning](https://semver.org/); changes follow
[Conventional Commits](https://www.conventionalcommits.org/) with scope `plugin`.

<!-- next-version -->

## plugin/v0.1.0 (2026-10-02)

### feat

- initial opencode plugin: registers the local ember MCP server (`advise` tool) with opencode
- resolves `ember-mcp` from `EMBER_MCP`, uv-tool bin dir, or Homebrew candidates
- passes explicit `PATH` so opencode launched from a GUI finds the binary
