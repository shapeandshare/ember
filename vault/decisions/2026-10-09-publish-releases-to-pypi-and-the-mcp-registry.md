---
title: Publish releases to PyPI and the MCP Registry, and retire the plugin release track
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/opencode
  - domain/mcp
  - status/draft
created: "2026-10-09"
updated: "2026-10-09"
code-refs:
  - .github/workflows/release-ember.yml
  - pyproject.toml
  - server.json
  - .claude-plugin/marketplace.json
  - packages/claude-plugin/.claude-plugin/plugin.json
  - ember/claude/claude_config.py
  - tests/test_distribution.py
---

# Publish releases to PyPI and the MCP Registry, and retire the plugin release track

Part of [[ember]]. Installs now pin a release, every release goes to PyPI (as `ember-advise`) and
the official MCP Registry, Claude Code users get a plugin marketplace, and the opencode
plugin stops versioning separately. Supersedes
[[2026-10-02-publish-as-gut-and-opencode-ember-advise]] and
[[2026-10-04-version-components-separately]].

## Context

- The documented install was `git+https://github.com/shapeandshare/ember` with no ref, so
  users got `main`'s head: on 2026-10-09 that was five commits past `v0.6.0`, and
  `ember --version` reported `0.6.0` for code that was not in it.
- The release workflow built a wheel and sdist for every GitHub Release, but nothing
  published them, while README, CONTRIBUTING, and AGENTS.md said "PyPI wheel" and the
  plugin README told users to add `{"plugin": ["opencode-ember-advise"]}`, which is not on
  npm.
- `gut` looked free on PyPI but is an empty project owned by another account; see
  [[2026-10-09-pypi-json-api-hides-empty-projects]].
- `ember init --opencode` already writes the opencode plugin users run, so the npm
  package's own versions, changelog, and workflow served no installer.
- The release sdist was 16.5 MB: hatchling included the whole repository.

## Decision

- Rename the distribution `gut` → `ember-advise`, with an `ember-advise` console-script
  alias for `ember.cli:main`; the `ember`, `gut`, and `ember-mcp` commands stay.
- Pin the git installs in `README.md` and `site/index.md` to `@v<version>`; commitizen
  `version_files` rewrites them, `server.json`, and the Claude Code plugin manifest on
  every bump, and `tests/test_distribution.py` fails when one drifts.
- Add job `publish-pypi` to `release-ember.yml`: it downloads the GitHub Release's files
  and runs `uv publish --trusted-publishing always --check-url https://pypi.org/simple/`
  in environment `pypi` with `id-token: write`. No PyPI token exists; PyPI's trusted
  publisher names the workflow file and environment.
- Add job `publish-mcp-registry` after it: `server.json` (`io.github.shapeandshare/ember`,
  PyPI `ember-advise`, run as `uvx --python 3.12 ember-advise mcp`), `mcp-publisher` v1.8.1 pinned by
  SHA-256, `login github-oidc`, and a short retry for PyPI propagation. Ownership is the
  `<!-- mcp-name: io.github.shapeandshare/ember -->` line in `README.md`.
- Ship a Claude Code marketplace in this repository (`.claude-plugin/marketplace.json`,
  name `ember`) listing `packages/claude-plugin/`: an inline `mcpServers.ember` running
  `ember-mcp`, and a byte-for-byte copy of the kit's `SKILL.md`, because a plugin cannot
  reference files outside its own directory. `ember doctor` reads
  `enabledPlugins["ember@ember"]` from the user, project, and local settings files.
- Restrict the sdist to `ember/`, `README.md`, `LICENSE`, and `THIRD_PARTY_NOTICES.md`
  (86 KB); the wheel built from it is unchanged.
- Retire the opencode plugin's release track: delete `release-plugin.yml`, the commitizen
  `plugin` config, and `make release-plugin`. Keep `packages/opencode-plugin/` and its
  node tests; its `package.json` stays at `0.4.0`.
- Not adopted: a Homebrew tap (torch on pinned Python 3.12 as a formula), a CUDA container
  image (CUDA unverified on hardware; Outerbounds builds from `requirements.txt`), and a
  bundled app or MCPB (the weights are not redistributed).

## Consequences

- Before the first upload, a maintainer must create the pending trusted publisher on
  pypi.org (project `ember-advise`, owner `shapeandshare`, repository `ember`, workflow
  `release-ember.yml`, environment `pypi`). A pending publisher does not reserve the
  name, so do it right before the next release.
- Existing `gut` tool installs must run `uv tool uninstall gut` before installing
  `ember-advise`: both provide the same commands.
- After the first PyPI release, switch the README and landing-page install to
  `uv tool install --python 3.12 ember-advise` and keep the pinned git form as an alternative.
- A bump PR opened before `version_files` existed (PR #84, `release v0.7.0`) leaves the
  pins at `0.6.0` and fails `tests/test_distribution.py`; re-dispatch `make release-ember`
  to regenerate it.
- PyPI files and registry versions are immutable; a failed upload is retried by
  re-running the failed job.
- Claude Code names a plugin server's tool `mcp__plugin_ember_ember__advise`, not
  `mcp__ember__advise`; the kit text still names the latter.
- Registry clients launch `uvx --python 3.12 ember-advise mcp`, which resolves the torch stack on
  first launch and still needs `ember model pull` before the first advise call.
- The site's install pin moves only when the site redeploys: bump merges are made by
  `GITHUB_TOKEN`, which starts no workflows.
