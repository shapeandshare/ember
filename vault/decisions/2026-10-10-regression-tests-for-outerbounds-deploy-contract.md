---
title: "Regression tests tying the Outerbounds deploy contract to server.py and requirements.txt"
type: decision
tags:
  - type/decision
  - domain/server
  - domain/tooling
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - tests/test_http_api.py
  - tests/test_freeze_deployment_requirements.py
  - deployment/flash.yaml
  - deployment/requirements.txt
  - ember/serving/server.py
  - scripts/freeze_deployment_requirements.py
---

# Regression tests tying the Outerbounds deploy contract to server.py and requirements.txt

Part of [[ember]]. Added two regression tests closing the exact class of gap that blocked
the Outerbounds redeploy twice in one session
([[2026-10-10-fast-bakery-strips-ember-advise-from-deploy-requirements]],
[[2026-10-10-remove-t004-non-loopback-auth-check]]): a committed deployment artifact
(`deployment/deploy.yaml`'s declared environment, `deployment/requirements.txt`'s package
list) silently diverged from what `server.py`/the packaging pipeline actually required, and
nothing in the test suite checked the real committed files against the real runtime
behavior — only synthetic fixtures.

## Context

Asked `ember_advise` (`best_next_step` choice question) which of six candidate follow-ups was
highest-value given the session's own trail: a test tying `deploy.yaml`'s real env vars to
`server.py`'s `lifespan()` scored highest (P=0.42, "high value" on an independent score
question, 2.6/4) — directly ahead of a `requirements.txt` completeness precheck (P=0.33).
Scope-creep risk on doing more than one or two of the six candidates scored moderate
(P=0.62), so only these two were pursued; redeploying with the latest client-side fixes,
closing the separately-tracked T-006 finding, and adding deployment monitoring were
explicitly deferred as out of scope for this session (see the conversation for the full
candidate list and reasoning).

## Decision

- **`tests/test_http_api.py::test_lifespan_accepts_deploy_yaml_environment_as_committed`**:
  parses `deployment/deploy.yaml`'s `environment:` block with `pyyaml` (already a transitive
  dependency — no new dependency added) and asserts `server.py`'s `lifespan()` does not raise
  under those exact values. `hosted.resolve` and `models.resolve_dir` are both mocked to
  `None` so the test exercises only the startup-refusal class of behavior (host/auth checks,
  config validation) — the Article XIV "model not found, start unloaded" pit-of-success
  path — never real S3/network/CUDA work, keeping it a fast, host-safe unit test.
  Confirmed this test fails with the exact production error (`RuntimeError: EMBER_HOST=
  '0.0.0.0' is a non-loopback address...`) when run against `server.py` as it stood before
  the T-004 removal (`git show a5eedfd^:ember/serving/server.py`), proving it would have
  caught that regression before it shipped. Any future startup-time guard added to
  `lifespan()` is now automatically checked against the real, committed deployment artifact,
  not just synthetic env vars chosen to match whatever the guard happens to check today.
- **`tests/test_freeze_deployment_requirements.py::test_committed_requirements_file_has_the_ember_advise_pin`**:
  reads the real, committed `deployment/requirements.txt` (not a tmp-path fixture) and
  asserts exactly one `ember-advise==<version>` line is present. Confirmed failing when the
  pin is stripped from the real file. Catches the case where `make deployment-requirements`
  is simply forgotten before a commit, the file is hand-edited, or
  `scripts/freeze_deployment_requirements.py`'s pin logic regresses — all three independent
  of whether `uv export`'s own flags ever change again.

## Consequences

- Both tests run in `make check`/CI (no model load, no network, no CUDA requirement), so they
  gate every PR rather than only being caught at the next live `make deploy`.
- `test_lifespan_accepts_deploy_yaml_environment_as_committed` will need its mocks revisited
  if `lifespan()`'s control flow changes meaningfully (e.g. if `models.resolve_dir`/
  `hosted.resolve` stop being the only two paths) — it is coupled to the current shape of
  `lifespan()`, not just its environment-variable contract, which is an intentional trade-off
  to keep the test fast and host-safe rather than attempting a full hosted-path integration
  test.
- Explicitly deferred (per the `ember_advise` consult): redeploying the live pod with the
  latest client-side (`0.10.x`) fixes baked in — not urgent, since nothing server-side
  changed since the `0.9.1` image currently running; closing T-006 (config file integrity,
  a separate pre-existing STRIDE finding); and deployment monitoring/alerting, which is new
  infrastructure rather than a fix to something broken (Article XV/YAGNI).

## References

- [[2026-10-10-fast-bakery-strips-ember-advise-from-deploy-requirements]] — the first gap this closes.
- [[2026-10-10-remove-t004-non-loopback-auth-check]] — the second gap this closes.
- [[2026-10-10-remote-health-probe-sent-no-auth-header]] — a third, independent bug found the
  same session (client-side CLI, not a deployment-contract gap — no new regression test
  needed beyond the one already added in that fix).
