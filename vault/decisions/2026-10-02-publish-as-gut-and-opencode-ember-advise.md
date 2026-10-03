---
title: Publish as gut on PyPI and as opencode-ember-advise on npm
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/opencode
  - status/draft
created: 2026-10-02
updated: 2026-10-02
code-refs:
  - pyproject.toml
  - packages/opencode-plugin/package.json
  - .github/workflows/ci.yml
---

# Publish as gut on PyPI and as opencode-ember-advise on npm

Part of [[ember]]. The Python distribution and the npm plugin package can't be named
ember, so they take the names below. Everything else stays ember.

## Context

`ember` is taken on PyPI and `opencode-ember` is taken on npm; see
[[2026-10-02-ember-names-are-taken-on-pypi-and-npm]].

## Decision

- The Python distribution is `gut`. Install it with
  `uv tool install --python 3.12 "gut @ git+https://github.com/shapeandshare/ember"`
  and remove it with `uv tool uninstall gut`. The commands stay `ember`, `gut`, and
  `ember-mcp`, and the import package stays `ember`.
- The npm plugin package is `opencode-ember-advise`, after the skill name.

## Consequences

- CI installs `dist/gut-*.whl`, and `ember uninstall` tells users to run
  `uv tool uninstall gut`.
- Neither package is published yet. Both names were free on 2026-10-02.
