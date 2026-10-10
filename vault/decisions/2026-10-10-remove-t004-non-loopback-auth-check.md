---
title: "Remove T-004's non-loopback-without-auth startup check"
type: decision
tags:
  - type/decision
  - domain/server
  - domain/governance
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - ember/serving/server.py
  - tests/test_http_api.py
  - docs/stride-tracker.csv
  - docs/stride-review.md
  - SECURITY.md
  - deployment/deploy.yaml
  - deployment/README.md
---

# Remove T-004's non-loopback-without-auth startup check

Part of [[ember]]. Removed `server.py`'s `lifespan()` check (added as STRIDE finding T-004,
PR #92) that raised `RuntimeError` at startup whenever `EMBER_HOST` resolved to a non-loopback
address with `EMBER_SERVER_AUTH_TOKEN` unset — direct maintainer instruction, after the check
turned out to make the already-documented, already-committed Outerbounds deployment
unstartable.

## Context

Redeploying `deployment/deploy.yaml` to Outerbounds (to pick up the
[[2026-10-10-fast-bakery-strips-ember-advise-from-deploy-requirements]] fix) surfaced a second,
unrelated failure once the first was fixed: the pod's `ember serve` process raised

```
RuntimeError: EMBER_HOST='0.0.0.0' is a non-loopback address but EMBER_SERVER_AUTH_TOKEN is
not set. Serving an unauthenticated inference endpoint beyond loopback removes the only
security boundary. Either bind to 127.0.0.1 or set EMBER_SERVER_AUTH_TOKEN.
```

`deployment/deploy.yaml` sets `EMBER_HOST: "0.0.0.0"` (required — Outerbounds routes traffic to
a fixed container port) and deliberately ships `secrets: []`, relying entirely on Outerbounds'
own `auth.type: API` gateway (every platform user's existing token) to gate access — this is
explicitly documented in `deployment/README.md` and in `deploy.yaml`'s own comments, and
predates T-004 by two days (`deployment/deploy.yaml` was added 2026-10-08 in PR #78/#86-era
work; T-004 landed 2026-10-09 in the STRIDE batch PR #92). Nobody reconciled the two: T-004's
check has no way to know a non-loopback bind is actually sitting behind a platform gateway that
authenticates every request before it reaches the pod, so it fails closed unconditionally.

Investigation (see `tests/test_http_api.py` for the behavior before this change, and
`docs/stride-review.md`'s now-updated Scan History) found the check was the *only* mechanism
enforcing this, added in the large 11-threat STRIDE remediation batch with no dedicated vault
note of its own — unlike this repo's established pattern (e.g. Article V's `wontfix` downgrade
of S-002/T-001/E-001, which got both a constitution amendment and a vault decision note).

Direct maintainer instruction: remove the check, record it in the threat model as `wontfix`
with a reason, and clean up the docs that referenced it.

While researching T-004's full scope, also found a **pre-existing, unrelated documentation
defect**: `docs/stride-review.md`'s detailed "Detailed Threat Register" section contained a
second, different finding ("Config file loaded without integrity check") that was also labeled
T-004 — an ID collision never caught because `docs/stride-tracker.csv` (the canonical tracker)
never had a duplicate row for it. Fixed in the same change by renumbering that finding to T-006
(content and `open` status unchanged) to avoid ambiguity now that the real T-004 is
`wontfix`.

## Decision

- **`ember/serving/server.py`**: removed the `lifespan()` check and its now-unused
  `is_loopback_host` import. A non-loopback `EMBER_HOST` now starts unconditionally, with or
  without `EMBER_SERVER_AUTH_TOKEN`. `is_loopback_host` itself is untouched — it has three
  other call sites (`ember/cfg/endpoint.py`'s client-side `Endpoint.resolve()`,
  `ember/commands/endpoint.py`'s scheme-guessing heuristic, `ember/commands/doctor.py`'s
  reporting) that are unrelated to this server-side enforcement and still need it.
- **Tests** (`tests/test_http_api.py`): the TDD red-phase test
  `test_lifespan_allows_non_loopback_host_without_auth` replaces
  `test_lifespan_raises_on_non_loopback_host_without_auth`, asserting the server now starts
  successfully in that configuration. `test_lifespan_allows_non_loopback_host_when_auth_is_enabled`
  and `test_lifespan_allows_loopback_host_without_auth` are kept as regression guards (bearer
  auth still works as defense in depth; the default loopback path is unaffected).
- **`docs/stride-tracker.csv` / `docs/stride-review.md`**: T-004 flipped `fixed` → `wontfix`,
  cross-referenced to this note, with a `first_seen`/`last_confirmed` history preserved and a
  new Scan History row recording the regression (per this repo's own documented STRIDE
  workflow: `fixed → open`/`wontfix` is an explicit, logged transition, not a silent edit).
  The colliding config-integrity finding renumbered `T-004` → `T-006` throughout (flat table,
  detailed register, coverage map, recommendations) — a documentation-only fix, unrelated in
  substance to the T-004 removal itself.
- **`SECURITY.md`**: added T-004 to the "Accepted residual risks" section, following the exact
  pattern already used for S-003/I-005/I-006/R-005 — a non-loopback bind with no
  `EMBER_SERVER_AUTH_TOKEN` is now an explicit, named accepted risk, not silently
  unaddressed.
- **`deployment/README.md`**: added a one-line cross-reference from the already-correct
  "`EMBER_SERVER_AUTH_TOKEN` intentionally left unset" explanation to the STRIDE entry and
  `SECURITY.md`, so a future reader can trace why that configuration is safe to ship.
- **No constitution amendment.** No Article names this specific mechanism (Article I governs
  the *default* being loopback and remote being opt-in — unaffected; it does not mandate a
  bearer-token-or-refuse enforcement once an operator opts into a non-default `EMBER_HOST`).
  Unlike the Article V precedent, this is an implementation detail of a non-named mechanism,
  not a stated principle, so a vault decision note is the appropriate record per this repo's
  own governance rules.
- **`README.md`/`COMPATIBILITY.md`**: no changes needed — both already described
  `EMBER_SERVER_AUTH_TOKEN` as "recommended" rather than mandatory, which was inconsistent with
  T-004's hard-fail until now and is accurate again.

## Consequences

- Any operator who sets `EMBER_HOST` to a non-loopback address is now responsible for its own
  access control (ember's token, a reverse proxy, or a platform gateway like Outerbounds'
  `auth.type: API`) — ember will not stop them from exposing an unauthenticated endpoint. This
  is a real, intentional widening of what ember will run without complaint; it trades a
  fail-fast guardrail for compatibility with gateway-authenticated hosted deployments that
  ember cannot detect from inside the pod.
- The Outerbounds deployment (`deployment/deploy.yaml`) is no longer blocked by this check;
  it was the motivating case and should now redeploy successfully (modulo the actual model
  load, which is addressed separately in the same redeploy session).
- The STRIDE threat model's `fixed` count for this scan period decreases by one and its
  `wontfix` count increases by one; anyone later proposing to re-add host enforcement should
  read this note and `SECURITY.md`'s new accepted-risk entry first, and should design any new
  check to recognize a trusted-gateway case rather than failing closed unconditionally.
- The T-004/T-006 ID collision in `docs/stride-review.md` is fixed; `docs/stride-tracker.csv`
  was never affected (it's the canonical source and never had the duplicate), so no data was
  actually lost — only the markdown's "Detailed Threat Register" and "Coverage Map" sections
  needed correction.
