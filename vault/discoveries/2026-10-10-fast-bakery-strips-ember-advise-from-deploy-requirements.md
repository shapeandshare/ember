---
title: "Fast Bakery never installs ember-advise itself, so ember serve fails with command not found"
type: discovery
tags:
  - type/discovery
  - domain/tooling
  - domain/cli
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - scripts/freeze_deployment_requirements.py
  - deployment/deploy.yaml
  - deployment/requirements.txt
  - shared/release.mk
---

# Fast Bakery never installs ember-advise itself, so ember serve fails with command not found

Part of [[ember]]. The hosted Outerbounds deployment failed at container start with
`./_ob_app_run.sh: line 2: ember: command not found` — `deploy.yaml`'s `commands: [ember
serve]` has no `ember` executable to run.

## What was tested

Traced the actual deploy pipeline: `make deployment-requirements` runs `uv export
--no-dev --no-editable --no-hashes --no-emit-project -o deployment/requirements.txt`,
then `scripts/freeze_deployment_requirements.py` strips PEP 508 markers for Fast
Bakery's parser. Checked the generated file for an `ember-advise` line:

```
$ grep -n "^ember-advise==" deployment/requirements.txt
(no matches)
```

Read Outerbounds' Fast Bakery contract (`deployment/deploy.yaml`'s own comments, and
`docs.outerbounds.com`): `dependencies.from_requirements_file` is `pip install`ed
verbatim; `--package-src-path .` only copies source files into the image at matching
paths — it does **not** `pip install -e .`/`pip install .` on that copied tree. So
nothing in the hosted pipeline ever installs the `ember-advise` distribution itself,
only its third-party dependencies (torch, transformers, fastapi, boto3, …).

## Finding

`--no-emit-project` is the specific `uv export` flag causing this: it deliberately
*excludes* the current project's own package from the export, on the assumption that
something else installs it (normally: an editable dev install already on `PYTHONPATH`).
In the Outerbounds deploy, nothing provides that "something else" — Fast Bakery starts
from a bare interpreter and only `pip install`s the requirements file plus copies raw
source. The pre-existing vault note
([[2026-10-08-outerbounds-deployment-and-cuda-support]]) already states the *intended*
behavior ("`--no-editable` so the export installs ember itself from the packaged source
tree (`pip install .`)") but that intent was never actually realized: `--no-editable`
only changes how an editable/path requirement is *expressed* if one were emitted —
`--no-emit-project` suppresses it from being emitted at all. The two flags were conflated
when the deploy config was written.

Because `ember-advise` is absent, the container has no `[project.scripts]` entry points
(`ember`, `gut`, `ember-mcp`), so `commands: [ember serve]` fails immediately with
`command not found`, before any model loading or server code runs.

## Relevance

Fixed in `scripts/freeze_deployment_requirements.py` (TDD, `tests/
test_freeze_deployment_requirements.py`): after resolving markers, the script now reads
`pyproject.toml`'s `[project].version` and appends an explicit `ember-advise==<version>`
line unless one is already present — idempotent across re-runs. This makes
`deployment/requirements.txt` match the design intent that was documented but not
implemented. Anyone touching `make deployment-requirements`, `deploy.yaml`'s `commands:`,
or the `uv export` flags should re-verify this line survives — a future `uv export`
change (e.g. dropping `--no-emit-project`) could silently make this appending step
redundant or (if `uv` starts emitting a local path/editable reference instead) actively
wrong, since Fast Bakery would then try to install a path that doesn't exist in the baked
image.

## References

- `vault/decisions/2026-10-08-outerbounds-deployment-and-cuda-support.md` — the original
  (incorrect) claim that `--no-editable` alone caused `pip install .` behavior.
- `scripts/freeze_deployment_requirements.py` — the fix.
- `deployment/deploy.yaml` line 50-51 — the `commands: [ember serve]` that surfaced this.
