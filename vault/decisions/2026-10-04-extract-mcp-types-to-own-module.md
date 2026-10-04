---
title: "Extract Question and AdviseInput from mcp_server.py to mcp_types.py"
type: decision
tags:
  - type/decision
  - domain/mcp
  - domain/tooling
  - status/reviewed
created: "2026-10-04"
updated: "2026-10-04"
code-refs:
  - ember/mcp/mcp_types.py
  - ember/mcp/mcp_server.py
  - .specify/memory/constitution.md
---

# Extract Question and AdviseInput from mcp_server.py to mcp_types.py

Part of [[ember]]. `ember/mcp_types.py` now holds the Pydantic wire types for the
`advise` MCP tool; `ember/mcp_server.py` imports from it. Resolves the §10.18
two-class migration debt on `mcp_server.py`.

## Context

Article X §10.2 mandates at most one primary class per file. `ember/mcp_server.py`
previously declared two Pydantic `BaseModel` classes inline:

- `Question` — the schema for a single typed question (`noul`/`choice`/`score`)
- `AdviseInput` — the top-level tool input wrapping `state`, `questions`, and
  optional media fields; its `questions` field is `dict[str, Question]`

This was tracked as migration debt in §10.18: "`ember/mcp_server.py` declares two
classes." The compliance pass (2026-10-04) paid this debt down.

## Decision

Both classes moved to a new module `ember/mcp_types.py` with its own NumPy-style
module docstring. `mcp_server.py` imports only `AdviseInput` from `.mcp_types`
(it uses `AdviseInput` as the tool parameter type; `Question` is only used as a
field type within `AdviseInput` itself — no direct caller in `mcp_server.py`).

`mcp_types.py` itself holds two classes. §10.2's exception covers only
"a tightly-coupled exception class raised only by that primary class." `Question`
is not an exception class — it is a Pydantic sub-schema field type. This is
therefore a remaining §10.2 technical violation, recorded in §10.18: "`ember/mcp_types.py`
declares two Pydantic models (`Question` and `AdviseInput`); `Question` is a
sub-schema field type of `AdviseInput` with no independent callers, satisfying the
spirit of §10.2's tight-coupling principle though not the letter of the exception."
Splitting into `question.py` + `advise_input.py` would add ceremony for no
readability gain on 66 lines of tightly coupled schema.

## Consequences

- `ember/mcp_server.py` has zero class definitions. ✅ §10.2 satisfied for that file.
- `ember/mcp_types.py` is the public location for the advise tool wire schema.
  Any consumer testing `Question`/`AdviseInput` directly imports from
  `ember.mcp_types`, not `ember.mcp_server`.
- §10.18 migration debt updated: two-class entry for `mcp_server.py` marked resolved;
  two-class entry for `mcp_types.py` added as a new tracked item.
- `make pr-ready` passes: ruff, mypy (15 source files), bandit, compile, 127 tests.
