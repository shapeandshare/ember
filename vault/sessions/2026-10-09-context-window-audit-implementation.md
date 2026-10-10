---
title: "Context window audit: implementation"
type: session-log
tags:
  - type/session-log
  - domain/runtime
  - domain/server
  - domain/agent-kit
  - domain/tooling
created: "2026-10-09"
updated: "2026-10-09"
---

# Context window audit: implementation

Part of [[ember]]. Implement `specs/003-context-window-audit/` with `/speckit.implement`,
test first, then finish the follow-ups found along the way.

## What happened

- **Counting and refusal.** `ember/serving/request_size.py` counts the whole request with
  upstream `encode_record` at `max_length=sys.maxsize`. `Engine._run_advise` refuses
  anything over the enforced limit with a 413 that states the token split, and turns a
  served answer whose `usage.input_tokens` differs from the count into a 500. The refusal
  reaches the agent through MCP byte for byte.
- **Limits.** `ember/serving/limits.py` resolves the effective maximum and the per-request
  cap with their sources (`LimitSource`, `GoverningLimit`). The load log, `/health`
  `engine`, and `ember doctor` (live, configured, or unknown) report them.
  `max_request_length` now defaults to unset, the loaded model's measured cap, which is
  32,768 until measured.
- **Two bugs found by running a real server.** `ember start` runs the server as
  `__main__`, so its logger fell outside `ember` and the INFO `limits:` line was dropped;
  `server.main` now routes `ember.*` through uvicorn's handler and the logger is named
  explicitly. The quickstart's unreachable-remote check used a loopback URL, which ember
  treats as local; it now uses `https://ember.invalid`.
- **Debt.** `pick_device`/`pick_dtype` moved to `ember/serving/devices.py` and the
  `media_kwargs` allowlist to `ember/serving/media.py`, taking `runtime.py` from 471 to
  386 lines; constitution 3.1.2 drops it from §10.18.
- **The long-context probe** (`evals/context/`, `ember eval context`,
  `make eval-context`) is built and unit-tested: records, padding to an exact length,
  memory sampling, scoring, the cap rule, a byte-for-byte summary, resume, reproduction,
  and snapshots. The filler is a vendored public-domain Moby-Dick
  (`THIRD_PARTY_NOTICES.md`).
- **Agent guidance.** The kit, the plugin's skill mirror, the snippet, README, and
  COMPATIBILITY say oversized requests are refused, never truncated;
  `tests/test_agent_kit.py` ties every quoted cap to the resolver.
- **Follow-ups done the same day.** The four `evals/eval/` scripts resolved their root one
  level too shallow (`parents[1]`), so `make eval-run` couldn't find its dataset; fixed.
  `provenance.json` now records the 31 packages added to `uv.lock` since its last refresh.
  The model-backed autostart test skips without weights. Doctor says "the server has not
  loaded a model yet" instead of "older ember" when `engine` is `null`.

## Decisions and discoveries written back

- [[2026-10-09-request-size-checks-miss-what-the-model-sees]] (resolution added)

## Follow-ups

- Run the canonical probe (`make eval-context`) on a clean tree, snapshot it, set
  `ModelSpec.max_request_length` for flash and full, and write the decision note that
  supersedes D-002 (tasks T060–T065).
