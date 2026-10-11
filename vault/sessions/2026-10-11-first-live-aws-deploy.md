---
code-refs:
  - deployment/aws/
created: 2026-10-11
tags:
  - type/session-log
  - domain/server
  - domain/tooling
  - status/draft
title: "Session: first live AWS GPU deploy — a chain of real-API failures"
type: session-log
updated: 2026-10-11
---
# Session: first live AWS GPU deploy — a chain of real-API failures

Part of [[ember]]. Taking the AWS GPU deployment (`specs/005-aws-gpu-deployment/`) from "preflight passes" to a running instance surfaced a chain of bugs, each invisible to the unit suite because the tests stubbed the very shapes the live API contradicts. This log records the arc; two findings have their own notes.

## What happened

1. **Tailscale OAuth scope** — the token exchange requested `dns` (read+write); the operator's client grants DNS *read* (`dns:read`), so Tailscale rejected the whole exchange. Fixed to `dns:read`. See [[2026-10-11-tailscale-oauth-scope-and-suffix]].
2. **Tailnet suffix** — no DNS endpoint exposes `<tailnet>.ts.net`; it is derived from a device's MagicDNS name. In the same note.
3. **`.env` handling** — `.env` added to `.gitignore`, `.env.example` created, `make setup` copies it, and the Makefile loads it (later reworked to load only unset variables).
4. **`Command` parameters leaked internal keys** — `Stack.create/update` sent every key of the params dict to CloudFormation, including the internal `_template_body` carrier → `Parameters: [_template_body] do not exist in the template`. A shared `_cfn_params` helper now skips `_`-prefixed keys (commit `1c86a76`).
5. **Named IAM capability** — the template names its role and instance profile, so `CAPABILITY_IAM` was insufficient (`InsufficientCapabilitiesException`); all three paths now pass `CAPABILITY_NAMED_IAM` (`5f7e0d8`).
6. **Non-ASCII template strings** — EC2 rejects non-ASCII in `GroupDescription`; the em dashes became hyphens and a test now rejects non-ASCII string values (`b0d85f3`).
7. **Root-cause failure reason** — `first_failure_reason()` returned the newest `CREATE_FAILED` event (a cascading "Resource creation cancelled"); it now returns the earliest — the actual cause (`6fe7338`).
8. **Capacity fallback** — `pick_subnet` returned one subnet; the requested AZ had no `g6e.xlarge` capacity. `pick_subnets` now returns every offering-AZ candidate and deploy retries the next one on a capacity failure (`a42c82c`).
9. **User data dropped by cloud-init** — unindented heredoc bodies made the rendered user data invalid YAML; cloud-init ran an empty config. See [[2026-10-11-cloud-init-dropped-invalid-user-data]] (`066d089`).

## State at the end of the session

- Stack `ember-default` is `CREATE_COMPLETE`; the instance runs in `us-west-2c` (after two AZs with no capacity), joined the tailnet as `ember-default`, and `tailscale serve` answers HTTPS.
- `ember-converge.service` fails on first boot, so `ember.service` never starts and `/health` returns `502`. **Open:** the cause is in the journal, blocked until the tailnet policy permits Tailscale SSH to `tag:ember` (now documented in `deployment/aws/README.md`, along with `aws-down` recovery for a `ROLLBACK_COMPLETE` stack).

## Relevance

The whole night's theme: **the deploy path was only ever exercised against mocks.** Every one of these nine bugs needed a real API call or a real boot to appear. Keep the live `make aws-up` in the loop when touching deployment code, and prefer asserting on the shapes the real service returns (scope lists, response bodies, template strings) over mocks that cannot contradict them.

## References

- `deployment/aws/` — the AWS GPU deployment package
- `vault/decisions/2026-10-11-aws-gpu-deployment-over-tailscale.md` — the feature decision
- Commits `1c86a76`, `5f7e0d8`, `b0d85f3`, `6fe7338`, `a42c82c`, `066d089`
