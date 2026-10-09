---
title: "PyPI's JSON API hides empty projects, and gut is one"
type: discovery
tags:
  - type/discovery
  - domain/tooling
  - domain/governance
  - status/draft
created: "2026-10-09"
updated: "2026-10-09"
code-refs:
  - pyproject.toml
  - server.json
---

# PyPI's JSON API hides empty projects, and gut is one

Part of [[ember]]. Both name checks (2026-10-02 and 2026-10-09) read
`https://pypi.org/pypi/<name>/json`, got 404, and concluded `gut` was free. It wasn't:
PyPI refused a pending trusted publisher for it with "This project already exists."
Corrects [[2026-10-02-ember-names-are-taken-on-pypi-and-npm]].

## What was tested

On 2026-10-09:

- `https://pypi.org/pypi/gut/json`: 404.
- `https://pypi.org/simple/gut/` (`Accept: application/vnd.pypi.simple.v1+json`): 200,
  `{"files": [], "versions": [], "project-status": {"status": "active"}}`, `_last-serial`
  1680587 (a serial from roughly a decade ago).
- XML-RPC `package_roles("gut")`: `Owner dantillberg`.
- The simple index returned 404 for `ember-advise`, `gut-feeling`, `ember-mcp`, and
  other candidates.

## Finding

- The JSON API answers 404 for a project that exists but has no releases. Such a name
  is still taken: uploads and pending publishers for it are refused.
- Check a name with the simple index instead: 404 means free, and 200 means taken, even
  with empty `files`. The PyPI project page sits behind a JavaScript challenge, so
  scripts can't use it.

## Relevance

- The distribution is now `ember-advise`; see
  [[2026-10-09-publish-releases-to-pypi-and-the-mcp-registry]].
- Getting `gut` would take the owner's consent or a PEP 541 request; neither is pending.

## References

- `pyproject.toml` (`name = "ember-advise"`), `server.json` (`identifier`)
