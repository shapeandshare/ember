---
title: "The deployed CUDA instance refuses requests the local cap allows"
type: discovery
tags:
  - type/discovery
  - domain/server
  - domain/tooling
  - status/draft
created: "2026-10-12"
updated: "2026-10-12"
code-refs:
  - deployment/aws/README.md
---

# The deployed CUDA instance refuses requests the local cap allows

Part of [[ember]]. The tag_assignment run against
`https://ember-default.tail5be351.ts.net` (g5.2xlarge, us-west-2b, an ember
0.12.0-era install) errored on 7 of 65 items while the same items passed
locally — the deployment enforces a lower per-request cap than the current
24,576-token fallback.

## What was tested

`ember eval run --category tag_assignment` with `EMBER_SERVER_URL` set to the
deployment: 58/65 items scored (80.1% [77.2, 83.1]); the 7 refusals are
exactly the items with states above 4,909 words (6.2k–8.5k), while every item
at or below that size passed.

## Finding

Checked the deployment's SSM config directly (2026-10-12): it already carries
`max_request_length: 24576` — the culprit is the **wheel**. The instance runs
`ember-advise==0.12.0`, which predates the per-model request caps
([[2026-10-10-per-model-request-caps]]) and the token-split refusal
semantics; the observed boundary (states up to 4,909 words passing, larger
ones refused) reflects that older server. The committed comparison pair
remains legitimate — both bundles record identical settings (`float16`,
`max_length 262144`, `max_request_length 24576` from the harness) — but the
CUDA halves' figures are depressed, and the error counts are recorded in the
bundles.

## Relevance

Upgrade the deployment to a current release
(`make aws-up EMBER_VERSION=<next>` reboots in place and converge installs
it) and re-run the legs — no configuration change is needed. More
generally: deployment configuration drifts invisibly until a long request
arrives — compare a deployment's `ember doctor` limits and version against
the released wheel after any release bump.

## References

- Run `17f0b0ad…_20261012T215829Z` (`results/`, `benchmark/`)
- `deployment/aws/README.md`, `specs/007-mined-vault-recipes/quickstart.md`
