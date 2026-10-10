---
title: "Split the Outerbounds deployment into flash.yaml and full.yaml, sized from the registry"
type: decision
tags:
  - type/decision
  - domain/models
  - domain/tooling
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - deployment/flash.yaml
  - deployment/full.yaml
  - deployment/README.md
  - shared/release.mk
  - tests/test_http_api.py
---

# Split the Outerbounds deployment into flash.yaml and full.yaml, sized from the registry

Part of [[ember]]. `deployment/deploy.yaml` (one file, implicitly `flash`) is renamed to
`deployment/flash.yaml` and joined by a new `deployment/full.yaml`, so each registry model
(`ember/models.py::REGISTRY`) can be deployed as its own Outerbounds App with compute sized
for that model specifically, ahead of actually deploying `full`.

## Context

Direct request to prepare a second deployment config for `full` and "ensure the compute is
accurate." `full` (27B, ~55 GiB of float16 weights) cannot share `flash`'s compute pool
(`ai-sage-inf-gpu`, confirmed only sized for `flash`'s ~18 GiB on a single A10G/24 GB GPU) —
sizing `full.yaml` from `flash.yaml` with bigger numbers on the same pool would not work;
it needs a fundamentally different GPU class. Argo CD and Slack sessions were both expired
during this session (no VPN), so `ai-sage-inf-gpu`'s exact underlying instance type could not
be confirmed directly; sizing instead comes from `ember/models.py`'s own declared
`memory_budget_bytes`/`approx_bytes` for `full` (96 GiB / 55 GiB) and COMPATIBILITY.md's
already-documented hardware table, cross-checked against AWS's own published GPU instance
specs (G5/A10G, G6e/L40S, P5/H100) via a web search, not against a live pool reading.

## Decision

- **Two files, one per registry model**: `deployment/flash.yaml` (renamed from
  `deployment/deploy.yaml`, `name: ember-flash`, real values preserved — the live
  deployment's actual S3 URI and `ai-sage-inf-gpu` compute pool) and `deployment/full.yaml`
  (new, `name: ember-full`). Outerbounds requires a globally unique `name` per deployment,
  confirmed via its own CLI reference docs.
- **`full.yaml`'s `resources` come from the registry, not a guess**: `memory: 96Gi` (matches
  `REGISTRY["full"].memory_budget_bytes` exactly — the same number the long-context probe's
  memory check already derived independently, see
  [[2026-10-10-per-model-request-caps]]), `disk: 100Gi` (`flash.yaml`'s 30Gi-for-18GiB ratio
  applied to `full`'s ~55 GiB of weights, rounded up).
- **`full.yaml`'s `compute_pools` is deliberately left commented out**, not pinned to
  `ai-sage-inf-gpu` or any other pool: `full`'s ~55 GiB of weights alone exceed every
  single-GPU option in the G5/G6e families (A10G 24 GB, L40S 48 GB) before activations or
  KV-cache are even counted. The only viable AWS single-GPU instance found is `p5.4xlarge`
  (1x H100, 80 GB HBM3, 256 GiB system RAM) — documented in both files' comments and
  `deployment/README.md`'s sizing table, but not yet confirmed to exist as an available
  compute pool in this workspace, so nothing is pinned until that's verified.
- **`ember` has no multi-GPU support** (`ember/serving/runtime.py::load_clef` moves the
  whole model to one device with `.to(device)`), so a multi-GPU instance like
  `p4d.24xlarge` (8x A100 40 GB) does not help `full` — confirmed by reading the loader
  before recommending any instance type, not assumed.
- **`make deploy`/`make undeploy` parameterized** by `EMBER_DEPLOY_MODEL` (default
  `flash`, preserving today's zero-arg behavior): `make deploy EMBER_DEPLOY_MODEL=full`
  selects `deployment/full.yaml` and (via the file's own `name:`) the right Outerbounds app.
  The pre-existing placeholder guard in `shared/release.mk` checked for a `<CONFIRM-` marker
  that never actually appeared in either file (dead code since the file was first written —
  confirmed by checking the original committed `deploy.yaml`); replaced with a check for the
  actual placeholder convention used (`your-bucket`/`your-prefix` in
  `EMBER_MODEL_S3_URI`), scoped to that field only (not `tags`, which the live `flash.yaml`
  deployment has never filled in and which doesn't affect correctness) so the guard doesn't
  retroactively break the working deployment.
- **Regression test extended, not duplicated**: `tests/test_http_api.py`'s
  `test_lifespan_accepts_deploy_yaml_environment_as_committed` (added in
  [[2026-10-10-regression-tests-for-outerbounds-deploy-contract]]) is parametrized over both
  `flash.yaml` and `full.yaml` instead of only checking one file, so a future
  `lifespan()` startup guard is checked against both deployments' exact declared
  environments.
- **Vault `code-refs` repaired, not rewritten**: five existing notes' frontmatter
  `code-refs: [deployment/deploy.yaml]` pointed at a file that no longer exists after the
  rename; updated to `deployment/flash.yaml` (the file those notes' events actually happened
  against). Their prose stays as originally written — it is an accurate historical record of
  what was true when `deploy.yaml` was still the only file, not something to retroactively
  rewrite into "flash.yaml" throughout.

## Consequences

- `deployment/deploy.yaml` no longer exists; any external bookmark, script, or CI step
  referencing that exact path breaks. Searched the whole repo (code, docs, Makefile,
  `.github/workflows/`) for the literal path before renaming; nothing outside `deployment/`,
  `tests/`, `scripts/`, and the five vault notes above referenced it, and all are now fixed.
- `full.yaml` cannot actually be deployed yet: its `EMBER_MODEL_S3_URI` is still a
  placeholder (no bucket has `full`'s weights uploaded as of this writing) and no
  compute pool is pinned. `make deploy EMBER_DEPLOY_MODEL=full` will correctly refuse with
  an actionable error until the S3 URI is filled in; the compute pool must be confirmed to
  exist and sized correctly (an 80 GB-class GPU) before a real deploy attempt — an
  undersized pool would be silently accepted by the Kubernetes scheduler (system RAM is
  the only thing validated at deploy time; GPU VRAM is not) and only fail later as a CUDA
  out-of-memory error inside the running pod.
- `ai-sage-inf-gpu`'s exact instance type is still unconfirmed directly (no Argo CD/Slack
  access this session) — `flash.yaml`'s existing `resources` already matched it empirically
  (per the file's own pre-existing comments about two earlier rejected pools), so this
  decision does not change flash's behavior, only adds full's sizing alongside it from
  first principles (the registry's own declared numbers).

## References

- `deployment/flash.yaml`, `deployment/full.yaml` — the two deployment contracts.
- `deployment/README.md` — the updated two-file sizing table and deploy instructions.
- `shared/release.mk` — `EMBER_DEPLOY_MODEL`-parameterized `deploy`/`undeploy` targets.
- `ember/models.py::REGISTRY` — the source of `full`'s `memory_budget_bytes`/`approx_bytes`.
- [[2026-10-08-outerbounds-deployment-and-cuda-support]] — the original single-deployment
  decision this supersedes for `full`.
- [[2026-10-10-per-model-request-caps]] — where `full`'s `memory_budget_bytes` (96 GiB) was
  independently derived, from the long-context probe's memory check.
- [[2026-10-10-regression-tests-for-outerbounds-deploy-contract]] — the test now
  parametrized over both files.
