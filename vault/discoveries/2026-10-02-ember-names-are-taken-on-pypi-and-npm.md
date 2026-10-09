---
title: The ember name is taken on PyPI and npm
type: discovery
tags:
  - type/discovery
  - domain/governance
  - domain/tooling
  - status/superseded
created: 2026-10-02
updated: 2026-10-09
code-refs:
  - pyproject.toml
  - packages/opencode-plugin/package.json
---

# The ember name is taken on PyPI and npm

> Superseded by [[2026-10-09-pypi-json-api-hides-empty-projects]]: `gut` was not free. Its
> JSON API 404s because the project has no releases; the distribution is now `ember-advise`.

Part of [[ember]]. The rename to ember collided with two package registries, and other
tools already install an `ember` command.

## What was tested

Registry metadata, checked on 2026-10-02:

- `https://pypi.org/pypi/ember/json`: a 0.0.1-dev placeholder ("Django REST Framework
  extensions for working with Ember.js") with no release files.
- `https://registry.npmjs.org/opencode-ember`: an unrelated opencode plugin (latest
  0.4.1, published 2026-10-01) that keeps LLM prompt caches warm by sending requests to
  the provider.
- `gut` and `gut-feeling` on PyPI, and `opencode-ember-advise` on npm, returned 404.

## Finding

- `pip install ember` or `uv tool install ember` can never install this project, and
  `{ "plugin": ["opencode-ember"] }` in an opencode config installs the other plugin.
- That plugin's install script links an `ember` command into `~/.local/bin`, the
  directory `uv tool install` uses for ours, and its npm package declares an `ember`
  bin. Ember.js's `ember-cli` installs an `ember` command too.

## Relevance

Publish under the names in [[2026-10-02-publish-as-gut-and-opencode-ember-advise]].
Keep the `gut` alias as the fallback when another `ember` command shadows ours.

## References

- `pyproject.toml` (the distribution `name`)
- `packages/opencode-plugin/package.json` (`"name": "opencode-ember-advise"`)
