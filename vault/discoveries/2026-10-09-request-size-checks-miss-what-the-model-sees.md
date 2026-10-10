---
title: "ember's size check counts a different request than the model sees"
type: discovery
tags:
  - type/discovery
  - domain/runtime
  - domain/mcp
  - domain/agent-kit
  - domain/governance
  - status/draft
created: "2026-10-09"
updated: "2026-10-09"
code-refs:
  - ember/serving/runtime.py
  - ember/serving/request_size.py
  - ember/serving/limits.py
  - evals/context/memory_sampler.py
  - ember/mcp/mcp_server.py
  - ember/agent_kit/ember-advise/SKILL.md
  - ember/cfg/config.py
  - specs/003-context-window-audit/research.md
---

# ember's size check counts a different request than the model sees

Part of [[ember]]. While planning `specs/003-context-window-audit/`, reading the code
against upstream showed that ember's per-request cap and the model's real input disagree.
It also surfaced four constraints that any future limit or error work has to respect.

## What was tested

- Read upstream `joint_schema_model.py` at both pinned revisions. The flash `17f0b0ad` and
  full `2f3de3dd` copies are byte-identical, 576 lines each.
- Read `ember/serving/runtime.py`, `ember/serving/server.py`, `ember/cfg/config.py`, and
  `ember/mcp/mcp_server.py`.
- Queried the torch 2.14 `torch.mps` API.
- Counted lines and bytes in `runtime.py` and the agent kit.

## Finding

1. **Upstream truncates silently.** `encode_record` tokenizes the prefix, the media
   prompt, the state, the schema, and the suffix as separate segments. When the request is
   over `max_length` (upstream default 16,384), it cuts the end of the state
   (`state_ids[: max_length - fixed_length]`) and gives no signal. Calling it with
   `max_length=sys.maxsize` returns the exact untruncated length. Because the segments are
   concatenated, differences between whole encodes split that total exactly into state,
   media, and fixed overhead.
2. **ember's pre-check counts the wrong thing.** It tokenizes `str(state)`. For a dict
   that is a Python repr, not the compact sorted JSON the model reads. It also ignores
   questions, schema, the prompt wrapper, and media, so images and video frames bypass the
   cap entirely. Today a negative `EMBER_MAX_REQUEST_LENGTH` silently disables the cap.
3. **The MCP layer rewrites slashes.** `_redact` turns any `/word` in a 4xx `detail` into
   `<path>`. An agent-facing error message must contain no `/` or `\`, or it arrives
   garbled.
4. **torch 2.14 on MPS has no peak-memory API.** There is no `max_memory_allocated` and no
   `reset_peak_memory_stats` (CUDA has both). Peak memory has to be sampled through
   `torch.mps.driver_allocated_memory()`.
5. **The skill has been wrong since D-002.** `SKILL.md` says inputs "are capped at the
   model's 262,144-token window". D-002 set a 32,768 per-request cap.
6. **`runtime.py` debt grew without being recorded.** The file is 471 lines; constitution
   §10.18 records 445.

## Relevance

- Count with upstream `encode_record` instead of re-deriving token counts, and keep agent
  error text free of path-like slashes.
- The 003 plan fixes 1, 2, 5, and 6 (see `specs/003-context-window-audit/research.md`,
  R1–R7), and samples MPS memory for 4 (R11).

## Resolution (2026-10-09)

The 003 implementation resolved the code findings:

- 1 and 2: `ember/serving/request_size.py` counts the whole request with upstream
  `encode_record` at `max_length=sys.maxsize`, and `Engine._run_advise` in
  `ember/serving/runtime.py` refuses anything over the enforced limit with a 413 that
  states the split. A served answer whose `usage.input_tokens` differs from the count is a
  500. A negative `EMBER_MAX_REQUEST_LENGTH` is now ignored with a warning
  (`ember/serving/limits.py`).
- 3: `refusal_message` contains no `/` or `\`; `tests/test_mcp_tool.py` asserts that the
  `ToolError` text arrives byte for byte.
- 4: `evals/context/memory_sampler.py` samples `driver_allocated_memory` on a thread.
- 5: `SKILL.md` now has a Size limits section; `tests/test_agent_kit.py` ties its numbers
  to the resolver.
- 6: `runtime.py` is 386 lines, and constitution 3.1.2 drops it from §10.18.

Still open: the per-model caps stay at the 32,768 fallback until a canonical
`make eval-context` run is snapshotted.

## References

- Upstream: `https://huggingface.co/Cloudflare/clef-flash/raw/17f0b0ad64efb65d273590632833508766b2aae6/joint_schema_model.py`
  (`encode_record` L103–197, `systemone` L547–576)
- `specs/003-context-window-audit/research.md` (R1, R2, R5, R6, R7, R11)
- `docs/stride-review.md` (D-002)
