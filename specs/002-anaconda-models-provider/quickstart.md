# Quickstart: Anaconda Models as a First-Class Preferred Provider

**Feature**: `002-anaconda-models-provider`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data model**:
[data-model.md](./data-model.md) | **Contracts**: [contracts/](./contracts/)

Runnable end-to-end validation scenarios for this feature, once implemented. Each scenario
maps to an acceptance scenario in `spec.md`. Replace `<anaconda-key>` with the actual registry
key chosen at implementation time (data-model.md leaves this as an implementation detail).

## Prerequisites

- Apple Silicon Mac, ember checked out and installed per `README.md` (`make bootstrap` or
  `uv tool install gut`).
- No prior `model` preference set (unset `EMBER_MODEL`, no `model` key in the config file, no
  `--model` flag) — this exercises the new default path (User Story 1).

## Scenario 1 — New default resolves to an Anaconda model (spec US1, AS1–AS2)

```sh
# Confirm no model override is set
unset EMBER_MODEL
ember config show | grep -i '"model"'   # should show the new Anaconda key, not "flash"

# Trigger the default model to load
ember model pull
# Expect: pulls/verifies the Anaconda-hosted entry, not Clef-flash from the public Hub

ember doctor
# Expect: the "model <anaconda-key>" line reports pulled/ready; selected model is the
# Anaconda entry
```

**Expected outcome**: the resolved and loaded model is the new Anaconda registry entry,
matching contracts/model-registry.md rule 10.

## Scenario 2 — Explicit Clef selection still works unchanged (spec US1 AS3, FR-003, FR-011)

```sh
EMBER_MODEL=flash ember doctor
# Expect: reports "flash" as the selected model, unaffected by the new default

EMBER_MODEL=flash ember model pull
# Expect: pulls Cloudflare's public clef-flash repo exactly as before this feature shipped
```

**Expected outcome**: explicit configuration overrides the default in both directions
(contracts/model-registry.md rule 11).

## Scenario 3 — List and select any registered model, Anaconda or Clef (spec US2)

```sh
ember model list
# Expect: JSON array including "flash", "full", and the new Anaconda entry, each with
# name/repo/params/kind/default/cached/path/bytes — same shape for every entry

# Pulling an Anaconda entry requires AWS S3 access to Anaconda's hosted platform
# bucket, set explicitly (never auto-detected). Credentials are OPTIONAL: when
# an IAM role is attached to the compute (e.g. Outerbounds), omit the two key
# vars entirely and boto3's default credential chain picks it up automatically.
export EMBER_ANACONDA_S3_ACCESS_KEY_ID=<issued-access-key>        # optional
export EMBER_ANACONDA_S3_SECRET_ACCESS_KEY=<issued-secret-key>    # optional
export EMBER_ANACONDA_S3_BUCKET=<hosted-platform-bucket-name>
ember model pull <anaconda-key>
EMBER_MODEL=<anaconda-key> ember start
# Expect: starts and serves /v1/systemone using the Anaconda entry

ember model rm <anaconda-key>
# Expect: removes local files exactly like `ember model rm flash` would
```

**Expected outcome**: an Anaconda entry is listable/pullable/selectable/removable through the
exact same commands as any Clef entry (contracts/model-registry.md rules 4–7, 9).

## Scenario 4 — Unknown model name still errors clearly (spec US2 AS3)

```sh
EMBER_MODEL=not-a-real-model ember model pull
# Expect: clear error listing valid registered names, now including the Anaconda key
```

## Scenario 5 — Anaconda-hosted endpoint (spec US3) — requires an issued endpoint/credential

```sh
# No local model pulled; point the client at an Anaconda-hosted endpoint
export EMBER_SERVER_URL="https://<anaconda-hosted-endpoint>"
export EMBER_AUTH_TOKEN="<issued-token>"

ember doctor
# Expect: "endpoint" line reports the configured remote Anaconda-hosted URL and reachability;
# clearly distinguishes "remote" from "local" (contracts/hosted-endpoint.md rule 7)

# Exercise advise through the MCP tool or CLI-equivalent path
# (see README.md's "Remote inference" section for the exact invocation)
```

**Expected outcome**: `advise` calls succeed against the hosted endpoint with the same
response shape as a local call; no local weights are required
(contracts/hosted-endpoint.md rules 1–7).

## Scenario 6 — No endpoint configured → unchanged local-only behavior (spec US3 AS3, FR-007)

```sh
unset EMBER_SERVER_URL EMBER_AUTH_TOKEN
ember doctor
# Expect: endpoint reports the default loopback URL; no outbound network call occurs beyond
# the explicit, user-initiated weight pull
```

**Expected outcome**: confirms the hosted-endpoint path is strictly opt-in
(contracts/hosted-endpoint.md rule 2; spec SC-005).

## Validation checklist

- [x] Scenario 1: fresh/unconfigured install defaults to an Anaconda model — verified
      2026-10-07: `config.resolve("model")` resolves to `anaconda-flash`.
- [x] Scenario 2: explicit `flash`/`full` selection is unaffected by the new default —
      verified: `EMBER_MODEL=flash ember doctor` reports `[ok] model flash`.
- [x] Scenario 3: `model list/pull/rm` treat Anaconda and Clef entries identically —
      verified: `ember model list` returns `flash`, `full`, and `anaconda-flash` in the
      same shape, with `anaconda-flash` correctly flagged `"default": true`.
- [x] Scenario 4: unknown-model error message includes the new Anaconda key — verified:
      `ember model pull not-a-real-model` →
      `error: "unknown model 'not-a-real-model'; choose from flash, full, anaconda-flash"`.
- [ ] Scenario 5: Anaconda-hosted endpoint serves `advise` end-to-end (requires an issued
      endpoint; run manually when credentials are available — not part of automated CI).
      The observability half (local-vs-remote labeling) is verified: `ember doctor` with
      `EMBER_SERVER_URL=https://anaconda-hosted.example` reports
      `[info] endpoint: remote https://anaconda-hosted.example (unreachable)`.
- [x] Scenario 6: unconfigured install makes no implicit remote network call — verified:
      `ember doctor` with no `EMBER_SERVER_URL` reports
      `[info] endpoint: local http://127.0.0.1:8765`, and
      `test_doctor_makes_no_remote_http_call_when_unconfigured` asserts
      `endpoint_cmd.remote_health` is never invoked.
