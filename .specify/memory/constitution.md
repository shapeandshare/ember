<!--
SYNC IMPACT REPORT — Distribution Renamed to ember-advise
Version change: 3.1.0 → 3.1.1 (PATCH: a naming fact is corrected; no principle changes)
Date: 2026-10-09
Reason: Publishing to PyPI failed: `gut` is an existing PyPI project (an empty one owned by
  another account), which its JSON API hid by returning 404. The distribution is renamed
  `ember-advise`; the product, package, CLI (`ember`, alias `gut`), and MCP names are
  unchanged, and an `ember-advise` console-script alias lets `uvx ember-advise mcp` start
  the MCP server.
Modified principles: none (Article XIV's default-path example and the naming constraint now
  name `ember-advise`)
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ pyproject.toml, uv.lock, server.json, release and CI workflows
  - ✅ README.md, AGENTS.md, CONTRIBUTING.md, THIRD_PARTY_NOTICES.md, site/index.md
  - ✅ vault/discoveries/ (new discovery note), vault/decisions/ (updated decision note)
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — CUDA Support Added for Outerbounds Hosted Deployment
Version change: 3.0.1 → 3.1.0 (MINOR: a new supported platform is added alongside MPS; the
  existing MPS/CPU behavior and Article VI's existing MUSTs are unchanged)
Date: 2026-10-08
Reason: Direct maintainer direction: ember will be deployed hosted on Outerbounds, and GPU
  support there is "absolutely" wanted, "full in scope" (not CPU-only for now). Outerbounds
  compute is Linux, not macOS — MPS is unavailable there by definition — so a hosted,
  GPU-accelerated deployment requires CUDA, which Article VI's original text explicitly
  scoped out "until this Article is amended." This amendment adds CUDA as a third supported
  device alongside MPS (still Apple-Silicon-only) and CPU (the universal fallback), with its
  own float16/bfloat16 dtype rule mirroring MPS's — CUDA has no equivalent of the
  `device_map={"": "mps"}` segfault MPS requires a workaround for, so CUDA loads normally
  via `device_map={"": "cuda"}` once weights are confirmed compatible.
Modified principles:
  - Article VI — retitled "Apple Silicon and CUDA"; CUDA added as a supported platform
    (float16 by default, matching MPS) alongside the existing MPS-first/CPU-fallback
    behavior, which is unchanged. The MPS-specific `device_map={"": "mps"}` segfault
    workaround remains MPS-only; it does not apply to CUDA's own `device_map={"": "cuda"}`
    loading path.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ ember/serving/runtime.py (pick_device/pick_dtype gain a cuda branch)
  - ✅ pyproject.toml (torch install docs for the CUDA wheel variant)
  - ✅ README.md / COMPATIBILITY.md (CUDA device docs, Outerbounds deployment)
  - ✅ deployment/ (new: deploy.yaml, requirements.txt generation)
  - ✅ vault/decisions/ (new decision note)
Follow-up TODOs: CUDA has not yet been verified against real NVIDIA hardware (no model-backed
  test run on CUDA exists at amendment time) — COMPATIBILITY.md records this as "not yet
  verified," matching the existing precedent for `full` on MPS.
-->
<!--
SYNC IMPACT REPORT — Simplification: ANACONDA_S3 Registry Subsystem Removed
Version change: 3.0.0 → 3.0.1 (PATCH: stale fact corrected in Article V's body text; the
  principle itself — ember supports any runnable model, REGISTRY is not a security gate —
  is unchanged)
Date: 2026-10-08
Reason: Direct maintainer pushback: "this is like shaving the yacht, do we actually need
  this level of complexity?" The `ANACONDA_S3` `REGISTRY`-entry subsystem (named
  `anaconda-flash`/`anaconda-clef` entries, a `ModelSource` enum, `s3_bucket`/`s3_prefix`
  fields, a shared `anaconda_s3_bucket` config key, and per-entry S3 dispatch in
  `pull()`/`resolve_dir()`/`remove()`) is removed entirely: `EMBER_MODEL_S3_URI` (added the
  same day) already solves the hosted-deployment case completely on its own, by bypassing
  `REGISTRY` entirely — a parallel named-registry path for the identical weights was
  unnecessary complexity on top of it. `REGISTRY` now holds only Hugging-Face-sourced entries
  (`flash`/`full`); `DEFAULT` reverted to `"flash"`. Article V's body text named `HUGGING_FACE`
  and `ANACONDA_S3` as the two model sources — `ANACONDA_S3` as a `REGISTRY`-entry source no
  longer exists, so that sentence is corrected to describe the actual two paths: `REGISTRY`
  entries (always Hugging-Face-sourced) and an operator-supplied `EMBER_MODEL_S3_URI`
  (independent of `REGISTRY`). No principle changed — this is a factual correction, not a
  redefinition, hence PATCH.
Modified principles:
  - Article V — corrected a stale implementation detail (removed the `ANACONDA_S3` source
    name, now described generically); the "any runnable model, no hash verification,
    REGISTRY is not a security gate" principle itself is unchanged.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ README.md / COMPATIBILITY.md (anaconda-flash/anaconda-clef removed; DEFAULT reverted)
  - ✅ specs/002-anaconda-models-provider/ marked superseded (spec.md, plan.md headers)
  - ✅ vault/decisions/ (new decision note)
Follow-up TODOs: none.
-->
<!--
SYNC IMPACT REPORT — Article V Redefined: Drop Mandatory Pinning, Support Any Runnable Model
Version change: 2.1.0 → 3.0.0 (MAJOR: Article V's core principle is redefined, not merely
  extended — the mandatory REGISTRY SHA-256 hash-verification requirement is removed)
Date: 2026-10-08
Reason: Direct maintainer direction: "we do not need pinned models as we will support any
  that can run and will likely not be able to manage/pin them all." ember is expected to run
  an open-ended set of models (hosted-S3-supplied, future REGISTRY entries, etc.) that cannot
  realistically each be hand-pinned with maintained SHA-256 hashes in `ember/models.py`. The
  2.1.0 amendment (same day) had already carved out a narrow, explicit, opt-in exception for
  exactly this reason on the `EMBER_MODEL_S3_URI` hosted path — this amendment generalizes
  that reasoning: unverified loading becomes the normal behavior for every model path, not an
  exceptional one requiring a second acknowledgment env var. `ModelSpec.revision` is kept
  (now optional) because it serves a distinct, non-security purpose — targeting a specific
  Hugging Face commit/branch/tag for `snapshot_download`, not verifying file integrity — and
  remains useful for the still-tested `flash`/`full`/`anaconda-flash`/`anaconda-clef` entries.
Modified principles:
  - Article V — retitled "Model Loading" (from "Reproducibility by Pinning"); the mandatory
    "MUST be pinned... in REGISTRY" + SHA-256 schema/head hash verification requirement is
    removed. `ModelSpec.revision` MAY optionally target a specific upstream commit/branch/tag
    for download purposes (not verified); dependency-range pinning (`uv.lock`, `uv sync
    --locked`) is UNCHANGED and still required — this amendment is scoped to model weights
    only, not the dependency-pinning half of the old Article V. The 2.1.0
    "Unverified hosted-deployment exception" paragraph (EMBER_MODEL_S3_UNVERIFIED=1 gate) is
    removed as redundant: there is no longer a verified default for it to be an exception to.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ ember/serving/integrity.py removed; ember/models.py, ember/serving/runtime.py,
    ember/serving/hosted.py, ember/serving/server.py, ember/serving/process.py,
    ember/commands/doctor.py simplified to match
  - ✅ README.md / COMPATIBILITY.md / AGENTS.md pinning language updated
  - ✅ vault/decisions/ (new decision note; the 2.1.0 exception note marked superseded, not
    deleted, per the vault's never-prune protocol)
Follow-up TODOs: none.
-->
<!--
SYNC IMPACT REPORT — Outerbounds Hosted Deployment: Explicit Unverified-URI Escape Hatch
Version change: 2.0.3 → 2.1.0 (MINOR: new, narrow exception added to Article V; the core
  pinning requirement is unchanged and still the default for every other path)
Date: 2026-10-08
Reason: Running ember as an Outerbounds-deployed app means the platform supplies the model's
  S3 location at deploy/start time (a single `s3://bucket/prefix` URI — matching
  `model-foundry`'s own S3-URI deployment convention, see
  `../model-foundry/src/api/storage/_base.py` and `deployment/deploy.dev.yaml`), not a
  REGISTRY key. A URI-only load has no way to supply a pinned revision/hash in advance, so
  loading it as-is would violate Article V's "MUST be pinned... in REGISTRY" as written. Per
  explicit human direction (not an agent-initiated weakening — Governance requires this),
  Article V gains a narrow, explicit, opt-in exception rather than a silent bypass: a second,
  distinct environment variable MUST be set to acknowledge the integrity trade-off, the
  resulting state MUST be visibly reported wherever the model is surfaced (never
  indistinguishable from a normal pinned load), and resolution happens once at process
  startup (fail-fast before serving), not lazily per-request.
Modified principles:
  - Article V — added the "Unverified hosted-deployment exception" paragraph: a
    `EMBER_MODEL_S3_URI` pointing at an S3 location MAY be loaded without a REGISTRY entry or
    hash verification, but ONLY when `EMBER_MODEL_S3_UNVERIFIED=1` is also set; absent that
    second variable, ember MUST fail fast at startup rather than silently falling back to a
    pinned entry or silently skipping verification. The loaded/reported model state MUST
    include an explicit "unverified" marker (`ember doctor`, `/health`) for as long as this
    path is active. This does not change the pinning requirement for any other path (REGISTRY
    entries, `EMBER_MODEL`, the existing `ANACONDA_S3`/`HUGGING_FACE` sources).
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ README.md / COMPATIBILITY.md (new env vars documented)
  - ✅ vault/decisions/ (new decision note recording this amendment's rationale)
Follow-up TODOs: none.
-->
<!--
SYNC IMPACT REPORT — Anaconda Models Feature: Migration Debt Paid Down
Version change: 2.0.2 → 2.0.3 (PATCH: migration-debt entry removed after being resolved in
  the same feature; no principle added, removed, or weakened)
Date: 2026-10-08
Reason: /speckit.implement on specs/002-anaconda-models-provider/ (tasks.md T032) split the
  S3-compatible download logic (`_s3_client`/`_download_anaconda_s3`, now
  `s3_client`/`download`) out of `ember/models.py` into a new module,
  `ember/cfg/anaconda_s3.py` — mirroring the existing precedent that `ember/cfg/paths.py`
  already owns `anaconda_s3_cache()`. `ember/models.py` is now 360 lines, under the Article X
  §10.3 400-line ceiling; the new module is 150 lines with 100% test coverage. The §10.18
  entry added for this debt earlier in the same feature (2.0.1 → 2.0.2) is removed per that
  Article's own "paid down as its file is next touched" rule — the debt no longer exists.
Modified principles:
  - Article X §10.18 — removed the `ember/models.py` (470 lines) entry added in the prior
    amendment; the file no longer exceeds the sizing ceiling.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ specs/002-anaconda-models-provider/plan.md (Constitution Check re-evaluation updated to
    "PASS (resolved 2026-10-08)"; Complexity Tracking table's sizing-violation row removed)
  - ✅ specs/002-anaconda-models-provider/tasks.md (T032 marked done)
Follow-up TODOs: none.
-->
<!--
SYNC IMPACT REPORT — Anaconda Models Feature: Migration Debt Recorded
Version change: 2.0.1 → 2.0.2 (PATCH: new migration-debt entry recorded; no principle added,
  removed, or weakened)
Date: 2026-10-08
Reason: /speckit.analyze on specs/002-anaconda-models-provider/ found that implementation
  (the ModelSource StrEnum + direct S3-compatible/boto3 download path added for Anaconda
  catalog entries) grew ember/models.py to 470 lines, over Article X §10.3's 400-line
  ceiling, without a corresponding §10.18 migration-debt record. Per §10.18's own rule
  ("known existing violations... never increased... recorded here"), a file that newly
  crosses the ceiling in a change must be recorded in the same change, not left silently
  growing. No principle text changed; this amendment only adds ember/models.py to the
  existing debt list, mirroring the existing runtime.py/evals/* entries.
Modified principles:
  - Article X §10.18 — added `ember/models.py` (470 lines) to the migration-debt list, with
    the originating feature and a suggested resolution (split the S3-compatible download
    logic into its own module) for a future contributor to pick up.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ specs/002-anaconda-models-provider/plan.md (Constitution Check re-evaluation already
    documents this finding as "CONDITIONAL PASS, action required")
  - ✅ specs/002-anaconda-models-provider/tasks.md (new follow-up task T032)
Follow-up TODOs: a future contributor splitting ember/models.py's S3-compatible download
  logic into its own module (e.g. ember/models_s3.py) should remove this entry from §10.18
  at that time, per the Article's own "paid down as its file is next touched" rule.
-->
<!--
SYNC IMPACT REPORT — Consistency Audit
Version change: 2.0.0 → 2.0.1 (PATCH: clarifications and stale facts; no principle added,
  removed, or weakened)
Date: 2026-10-06
Reason: a full audit of the constitution against the code and docs found internal
  contradictions and stale facts.
Modified principles:
  - Article VIII — lint list includes D; CI names ci.yml (ci-check.yml never existed in the
    tree); coverage paragraph defers to Article XI (it still said "not yet gated, 60%");
    commit types match commitizen.
  - Article X §10.11 — `# async-first:exception` listed among exception tags.
  - Article X §10.18 — cli.py was found at 1086 lines (the growth past 929 broke §10.18);
    nine unrecorded oversize modules recorded as debt; cli.py split and the two evals/
    magic-string sets converted to StrEnums, both then removed from the debt list.
  - Article XII — §12.1 defers to §12.2; deprecated `asyncio.get_event_loop` and the anyio-2
    `run_sync_in_worker_thread` name replaced with `anyio.to_thread.run_sync`; §12.3 matches
    the async `advise` tool; §12.4 made decidable.
  - Article XIII — diagram no longer places server.py in two layers; §13.1 names the imports
    the MCP layer may use; §13.5 locates defaults in ember/cfg/config.py.
  - Article XIV — §14.1 describes both the lifecycle refusal and the 503 path; §14.2 no
    longer implies support beyond Article VI; rationale de-absolutized.
  - 2.0.0 Sync Impact Report — doc-propagation tasks are T023–T025 (done), not T020–T022.
Added sections: none
Removed sections: none
  - Article XI §11.2 — floor ratcheted 71% → 81% (measured 81.93% by `make test-cov`).
Code changes in the same change: process.py audit-log warning uses logging (§10.13);
  evals result/snapshot writes are atomic (§10.17).
Templates / docs propagated:
  - ✅ AGENTS.md, README.md, CONTRIBUTING.md, SECURITY.md (CI description, commit types,
    in-scope files)
  - ✅ vault/discoveries/2026-10-06-constitution-consistency-audit.md
Follow-up TODOs: none. Resolved after the audit (same date): ember/cli.py split into
  ember/cli.py + ember/commands/; Condition and Tone enums in evals/ (§10.18 updated).
-->
<!--
SYNC IMPACT REPORT — Remote Inference (Article I redefinition)
Version change: 1.4.0 → 2.0.0 (MAJOR: Article I redefined from "Local-First and Private" to
  "Local-First by Default"; a single remote endpoint may be explicitly configured, in which
  case state, questions, and answers are sent to that endpoint by the user's own choice).
Date: 2026-10-06
Reason: feature 001-remote-inference-servers requires optional remote inference; the previous
  absolute network prohibition is incompatible with the feature and with removing the
  "never leaves your machine" documentation guarantee.
Modified principles:
  - Article I — renamed "Local-First by Default"; local remains the default and the only
    behavior of an unconfigured install; remote is opt-in via one configured endpoint.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ specs/001-remote-inference-servers/ (spec, plan, research, data-model, contracts, tasks)
  - ✅ README.md, SECURITY.md, RESPONSIBLE_USE.md, ember/agent_kit/* (tasks.md T023–T025; the
    original "T020–T022" citation was wrong and is corrected in 2.0.1)
  - ✅ AGENTS.md operationalization paragraph updated in this change
Follow-up TODOs: docs updates are tracked in the feature's tasks.md, not silently deferred.
-->
<!--
SYNC IMPACT REPORT — Five New Constitutional Articles
Version change: 1.3.5 → 1.4.0 (MINOR: Articles XI–XV added; coverage ratchet applied; async-first enforced)
Date: 2026-10-04
Modified principles:
  - Article VIII — coverage floor ratcheted from 60% to 71% (current measured level).
Added sections:
  - Article XI — Test-Driven Development & Coverage Ratchet
  - Article XII — Async-First
  - Article XIII — Layered Architecture
  - Article XIV — Pit of Success
  - Article XV — Simplicity First and YAGNI
Migration debt delta: none (server.py health() and metrics() converted to async def;
  systemone_endpoint() documented as async-first:exception for the engine lock).
Templates / docs propagated:
  - ✅ AGENTS.md (new sections for each article)
  - ✅ CONTRIBUTING.md (code style table updated)
  - ✅ ember/serving/server.py (health/metrics -> async def)
  - ✅ pyproject.toml (fail_under 60 -> 71)
  - ✅ vault/decisions/2026-10-04-constitutional-articles-xi-xv.md
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Sub-package Restructure
Version change: 1.3.4 → 1.3.5 (PATCH: §10.18 paths updated; §10.16 path updated; §10.3 compliance restored)
Date: 2026-10-04
Modified principles:
  - Article X §10.18 — Migration debt paths updated to reflect sub-package move:
    ember/serving/server.py, ember/mcp/mcp_server.py, ember/mcp/mcp_types.py;
    deferred imports updated to from .serving import server / from .mcp import mcp_server.
  - Article X §10.16 — Server schema path updated to ember/serving/server.py.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (project structure tree, watch-outs, MCP table, call-path paths updated)
  - ✅ README.md (project structure tree, call-path paths updated)
  - ✅ CONTRIBUTING.md (runtime.py → serving/runtime.py, mcp_server.py → mcp/mcp_server.py)
  - ✅ ember/ code (serving/, mcp/, cfg/, opencode/ sub-packages; all imports and -m paths updated)
  - ✅ evals/ code (render/, sections/, charts/ sub-packages; all imports updated)
  - ✅ vault/decisions/2026-10-04-restructure-into-sub-packages.md
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Package Ownership Policy Reinstatement
Version change: 1.3.3 → 1.3.4 (PATCH: §10.1 reverted from PEP 420 to explicit __init__.py ownership; root-only re-export rule added)
Date: 2026-10-04
Modified principles:
  - Article X §10.1 — Reverted from pure PEP 420 implicit namespaces back to the explicit
    __init__.py ownership policy. Every fully-owned package level MUST have an __init__.py.
    Sub-package __init__.py files are bare and docstring-only (no imports, no re-exports).
    The package root ember/__init__.py is the ONLY level permitted to re-export symbols.
    Data-only directory prohibition unchanged.
Added sections: none
Removed sections: none
Migration debt delta: ember/__init__.py restored (bare marker, MAY carry __version__ and
  re-exports from root); ember/agent_kit/__init__.py restored (bare docstring-only marker,
  no imports, no re-exports); ember/agent_kit/api.py retained as named API module;
  explicit_package_bases = true removed from pyproject.toml [tool.mypy].
Templates / docs propagated:
  - ✅ AGENTS.md (§10.1 bullet updated)
  - ✅ CONTRIBUTING.md (Package ownership row updated)
  - ✅ ember/ code (__init__.py files restored; api.py retained; no import site changes needed)
  - ✅ vault/decisions/2026-10-04-ownership-policy-reinstatement.md
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Implicit Namespace Packages Amendment
Version change: 1.3.2 → 1.3.3 (PATCH: §10.1 rewritten to mandate PEP 420 implicit namespaces)
Date: 2026-10-04
Modified principles:
  - Article X §10.1 — "Package ownership" rule rewritten: NO __init__.py anywhere under ember/
    (pure PEP 420 implicit namespaces). The previous rule required a bare docstring-only
    __init__.py at every fully-owned package level; that requirement is removed. The two
    exceptions (package root __version__ and agent_kit public API) are replaced by the
    instruction to place such code in a normal named module (e.g. api.py) inside the sub-package.
    Data-only directory prohibition carried forward unchanged.
Added sections: none
Removed sections: none
Migration debt delta: ember/__init__.py (bare marker) deleted; ember/agent_kit/__init__.py
  API code moved to ember/agent_kit/api.py; six import sites updated (ember/cli.py,
  ember/mcp/mcp_server.py, tests/test_agent_kit.py, tests/test_mcp_tool.py, tests/test_cli.py,
  evals/agent/sandbox.py).
Templates / docs propagated:
  - ✅ AGENTS.md (§10.1 bullet updated)
  - ✅ CONTRIBUTING.md (Package ownership row updated)
  - ✅ ember/ code (both __init__.py files removed; api.py created; imports updated)
  - ✅ vault/decisions/2026-10-04-implicit-namespace-packages.md
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Public Repository Clarification
Version change: 1.3.1 → 1.3.2 (PATCH: clarification, no principle change)
Date: 2026-10-03
Modified principles:
  - Development Workflow & Quality Gates — gate 3 names a maintainer's Apple Silicon machine
    for the model-backed suite; the repository is public and never uses a self-hosted runner.
    No requirement changes.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ README.md (public install note; `test-strict` no longer "for CI")
  - ✅ vault/decisions/2026-10-03-harden-github-before-going-public.md
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Agent Evaluation Clarification
Version change: 1.3.0 → 1.3.1 (PATCH: clarification, no principle change)
Date: 2026-10-03
Modified principles:
  - Article IV — clarifies that the opt-in agent evaluation (`ember eval agent`) may launch the
    opencode CLI inside an isolated sandbox; tests still MUST NOT. Approved by the maintainer.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (commands, watch-outs), README.md (Benchmark section)
  - ✅ vault/decisions/2026-10-03-measure-ember-through-the-agent.md
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Python Conventions Amendment
Version change: 1.2.0 → 1.3.0 (MINOR: new Article X)
Date: 2026-10-03
Modified principles:
  - Article VIII — unchanged; Article X refines it and defers to it where silent
Added sections:
  - Article X — Python Conventions
Removed sections: none
Migration debt:
  - Recorded inline as Article X §10.18; existing violations MUST NOT grow. One-class-per-file,
    no-loose-functions, and the 400-line ceiling remain prospective and tracked. NumPy
    docstrings (ruff `D`) and `ember/py.typed` are wired in this change and now enforced for
    `ember/`.
Templates / docs propagated:
  - ✅ AGENTS.md (new "Python conventions" section; watch-outs; truth table unchanged)
  - ✅ CONTRIBUTING.md (Code style section expanded with the same rules)
  - ✅ pyproject.toml ([tool.ruff.lint] selects `D`, `[tool.ruff.lint.pydocstyle]` numpy;
    tests/scripts exempt), ember/py.typed (zero-byte PEP 561 marker)
  - ✅ ember/ docstrings brought to NumPy compliance (66 → 0)
  - ✅ vault/decisions/2026-10-03-adopt-peer-python-conventions.md, vault/ember.md (hub link)
Follow-up TODOs:
  - Split `ember/cli.py` (788 lines) by responsibility to meet the Article X ceiling
  - Pay down one-class-per-file / no-loose-functions debt as files are next touched
-->
<!--
SYNC IMPACT REPORT — Project Memory Vault Amendment
Version change: 1.1.2 → 1.2.0 (MINOR: new Article IX)
Date: 2026-10-02
Modified principles: none
Added sections:
  - Article IX — Project Memory Vault
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (vault protocol; structure, commands, and watch-outs)
  - ✅ README.md (layout and make targets)
  - ✅ vault/ (hub, tag vocabulary, templates, first notes)
  - ✅ scripts/vault_audit.py, tests/test_vault_audit.py, shared/vault.mk
  - ✅ .opencode/opencode.json (vault MCP server), .opencode/commands/vault-health.md
  - ✅ provenance.json, PROVENANCE.md (wellspring-adapted scaffolding, mcpvault)
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Ember Rename Amendment
Version change: 1.1.1 → 1.1.2 (PATCH: product renamed to match the mascot, no principle change)
Date: 2026-10-02
Modified principles:
  - Articles I, III, VIII — names updated (`ember-mcp`, `ember://guide` resource,
    `ember-advise` skill, `ember/` package)
Added sections: none (the naming bullet in Additional Constraints now marks "gut feeling"
  as flavor text and names the `gut` distribution)
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (Naming section; names throughout)
  - ✅ README.md, CONTRIBUTING.md, DESIGN.md, SECURITY.md, SUPPORT.md (names, repository URLs)
  - ✅ ember/agent_kit/ (instructions, skill, snippet)
  - ✅ assets/brand/ (banner wordmark, titles, `--ember-*` tokens) and provenance.json
Follow-up TODOs: none (repository renamed to shapeandshare/ember; distribution is `gut`
  because `ember` is taken on PyPI)
-->
<!--
SYNC IMPACT REPORT — Naming Consolidation Amendment
Version change: 1.1.0 → 1.1.1 (PATCH: names and clarifications, no principle change)
Date: 2026-10-02
Modified principles:
  - Article III — artifact names updated (`advise` tool, `gut-feeling-advise` skill,
    `gut-feeling://guide` resource)
Added sections: none (one naming bullet added to Additional Constraints)
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (Naming section; names throughout)
  - ✅ README.md, CONTRIBUTING.md, DESIGN.md, SECURITY.md, SUPPORT.md (names)
  - ✅ gut_feeling/agent_kit/ (instructions, skill, snippet reframed as an advisor)
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Tooling & Quality Gates Amendment
Version change: 1.0.0 → 1.1.0
Date: 2026-10-02
Modified principles: none
Added sections:
  - Article VIII — Tooling and Code Quality
Removed sections: none
Migration debt: none (tooling config already added to pyproject.toml)
Templates / docs propagated:
  - ✅ AGENTS.md (new "Tooling" section added; commands table updated)
  - ✅ CONTRIBUTING.md (code style table, pr-ready gate, commit conventions)
  - ✅ DESIGN.md (tooling stack section, config-location section)
  - ✅ pyproject.toml ([tool.ruff], [tool.mypy], [tool.bandit], [tool.commitizen], [tool.coverage.*])
  - ✅ shared/python.mk (lint, format, typecheck, security, pr-ready targets)
  - ✅ .github/workflows/ci-check.yml (stub: lint + typecheck + security jobs)
Follow-up TODOs:
  - Enable ci-check.yml auto-trigger once `make pr-ready` is confirmed green on main
  - Ratchet coverage floor (currently 60%) upward as test coverage grows
-->
<!--
SYNC IMPACT REPORT — Constitution Ratification
Version change: template → 1.0.0 (initial ratification)
Date: 2026-10-02
Modified principles: n/a (template placeholders replaced)
Added sections:
  - Article I — Local-First and Private
  - Article II — Typed Decisions, Not Text
  - Article III — Agent-Legible Contract
  - Article IV — Lazy, Non-Interfering Lifecycle
  - Article V — Reproducibility by Pinning
  - Article VI — Apple Silicon First
  - Article VII — Verification Over Assertion
  - Additional Constraints
  - Development Workflow & Quality Gates
  - Governance
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (operationalizes this constitution; behavioral principles map to Articles)
  - ✅ CLAUDE.md (imports AGENTS.md)
  - ✅ README.md (agent onboarding section reflects Article III)
  - ⚠ .specify/templates/*.md (no change — the generic Constitution Check gate applies as-is)
Follow-up TODOs: none
-->
# ember Constitution

## Core Principles

### Article I — Local-First by Default

Inference MUST run on the user's machine **by default**, and the decision path
(`ember-mcp` → HTTP server → model) MUST NOT send `state`, questions, or answers over the
network **when no remote endpoint is configured**. A user MAY explicitly configure a single
remote inference endpoint; when one is configured, `state`, questions, and answers are sent to
that endpoint by the user's own choice. An unconfigured install remains local-only and the
default endpoint remains loopback. The only other network access is the explicit,
user-initiated weight download (`ember model pull`, `make download`). Model weights MUST stay
in the Hugging Face cache or a user-chosen directory, and MUST NOT be redistributed from this
repository.

Rationale: agents pass sensitive context (code, diffs, logs, user messages) into `state`, so
local stays the safe default and the core value proposition. Remote inference exists for users
who cannot host the model (memory, disk, or CI) and is opt-in, explicit, and reversible.

### Article II — Typed Decisions, Not Text

The product surface is calibrated probabilities over options the caller defines (`noul`,
`choice`, `score`), returned in the Jev/SystemOne response shape. The tool MUST NOT generate
free-form text, and the server MUST reject malformed questions with explicit errors (HTTP 422,
MCP tool errors) rather than guessing. New question types or response fields are API changes
(see Governance).

Rationale: bounded, machine-readable outputs are what make the model safe to wire into agent
control flow.

### Article III — Agent-Legible Contract

For consumers' agents, the tool name, input schema, field descriptions, MCP
`initialize.instructions`, the `ember://guide` resource, the `ember-advise` skill, and the
AGENTS.md snippet are the entire manual. Therefore:

- §3.1 All agent-facing guidance MUST live in `ember/agent_kit/` and be delivered from
  there; no channel may carry a divergent copy.
- §3.2 `instructions.md` MUST stay within 2048 bytes; the skill MUST satisfy the Agent Skills
  frontmatter contract (`name` matching its directory, `description` ≤ 1024 characters).
- §3.3 Thresholds and observed numbers in the kit MUST come from real model output and MUST be
  re-measured when the model revision or a recipe schema changes.
- §3.4 Changes to any of these artifacts MUST be reviewed as public-API changes and land with
  matching README and test updates.

### Article IV — Lazy, Non-Interfering Lifecycle

The model server SHALL start on demand (lazy autostart) and stay warm; nothing may run at
login or boot unless the user opts in. Tooling MUST only start, signal, or stop processes it
launched itself (tracked by PID) and MUST NOT kill by port or by pattern. Tests MUST bind random
free ports, MUST NOT use the default port 8765, and MUST NOT invoke the opencode CLI or modify
global opencode configuration. The opt-in agent evaluation (`ember eval agent`) is not a test:
it MAY launch the opencode CLI only inside a temporary sandbox with a private HOME and XDG
directories and no TCP port, MUST stop only the processes it launched, and MUST NOT run as part
of `make check`, `make test`, or CI.

Rationale: users run several opencode instances and their own servers on the same host.

### Article V — Model Loading

ember supports any model that can run under its loader contract (a
`Qwen3_5ForConditionalGeneration`-shaped backbone + `joint_schema_model.py` + a joint head),
not a hand-maintained allowlist of individually pinned, hash-verified weights. `REGISTRY`
entries (`ember/models.py`) are a directory of known-good Hugging Face Hub sources (name,
repo, size) for discoverability and `ember model pull`/`list`/`rm`, not a security gate —
`joint_schema_model.py` is imported and executed from whatever directory is resolved, with no
SHA-256 integrity check, for a `REGISTRY` entry or for an operator-supplied
`EMBER_MODEL_S3_URI` (a hosted deployment's own model location, independent of `REGISTRY` —
see `ember/serving/hosted.py`). A `ModelSpec` MAY set `revision` to target a specific Hugging
Face commit/branch/tag for `snapshot_download` — this is a download convenience, not a
verified pin, and MAY be left unset (fetches the repo's default branch).

Dependency ranges MUST still be anchored to tested versions, `uv.lock` MUST be committed, and
CI MUST install with `uv sync --locked` — this Article's dependency-pinning requirement is
unchanged; only the model-weight hash-verification requirement is removed. Bumping a model's
`revision` or widening a dependency range MUST be accompanied by green model-backed tests and
re-measured agent-kit numbers (§3.3) whenever the change could affect behavior.

### Article VI — Apple Silicon and CUDA

Three devices are supported: MPS (macOS on Apple Silicon, float16 — the local-first default),
CUDA (NVIDIA GPUs, float16 — the hosted-deployment path, e.g. Outerbounds compute, which is
Linux and has no MPS), and CPU (float32, the universal fallback available wherever torch
runs). `EMBER_DEVICE=auto` selects MPS or CUDA when available, else CPU.

Weights MUST be loaded on CPU and then moved to the target accelerator; `device_map={"":
"mps"}` MUST NOT be used for MPS (it segfaults with the pinned stack) — this constraint is
MPS-specific and does not apply to CUDA, which loads normally via `device_map={"": "cuda"}`.
Other accelerator platforms (e.g. AMD ROCm, Intel XPU) remain out of scope until this Article
is amended again.

### Article VII — Verification Over Assertion

Work is done when the evidence says so: `make check` passes before every commit, `make test`
passes for changes to the runtime, servers, CLI, or agent kit, and CI is green. User-visible
behavior MUST be exercised for real (CLI runs, MCP protocol calls, and an opencode end-to-end
check where integration changes), not inferred from reading code.

### Article VIII — Tooling and Code Quality

**Applicability**: Effective 2026-10-02. Fully applies; no migration debt.

All Python source in `ember/` MUST pass the following gates before a commit reaches
`main`:

- **Formatting**: `ruff format` (line length 88, double quotes). Run via `make format`.
- **Linting**: `ruff check` with rule sets E, F, I, N, W, UP, B, S, PT, RUF, and D (D is
  scoped to `ember/` by Article X §10.10). Run via `make lint`.
- **Type checking**: `mypy --strict` targeting `ember/`. Run via `make typecheck`.
- **Security**: `bandit -r ember/`. Run via `make security`.
- **Compile**: `python -m compileall -q ember scripts tests`. Run via `make compile`.
- **Unit tests**: `pytest -m "not model"`. Run via `make test-fast`.

The composite gate `make pr-ready` runs all of the above in order. It MUST pass before opening
a pull request. CI (`.github/workflows/ci.yml`) enforces format, lint, type checking, security,
and `make check` on every push and pull request.

All tool configuration MUST live in `pyproject.toml`. Separate tool config files (`ruff.toml`,
`mypy.ini`, `.bandit`, `.coveragerc`) MUST NOT be created; they scatter configuration and
create reconciliation debt.

Commit messages MUST follow Conventional Commits using the commitizen
`cz_conventional_commits` types (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`,
`ci`, `build`, `style`, `revert`), with the component scope defined in `AGENTS.md`. Version
bumps are managed by commitizen (`uv run cz bump`).

Coverage is gated by `fail_under` in `[tool.coverage.report]`; the floor and its ratchet are
governed by Article XI §11.2.

### Article IX — Project Memory Vault

The vault at `vault/` is the governed memory of this project's own development: decisions,
discoveries, and session logs. It complements `README.md`, `AGENTS.md`, `DESIGN.md`, and
`PROVENANCE.md`, and never duplicates or overrides them.

- §9.1 Every note outside `vault/_meta/` MUST carry frontmatter (`title`, `type`, `tags`,
  `created`, `updated`) and use only tags listed in `vault/_meta/tags.md`: exactly one
  `type/*` matching `type`, at least one `domain/*`, and at most one `status/*`. A new tag
  is added to that file before it is used.
- §9.2 Significant decisions and non-obvious discoveries MUST be written back as they occur,
  in the same change as the work behind them. Session logs are append-only. Routine changes
  and facts documented elsewhere MUST NOT get notes.
- §9.3 Every note MUST be reachable by wikilinks from the hub `vault/ember.md`, and every
  wikilink and `code-refs` path MUST resolve.
- §9.4 Agent-written notes start at `status/draft` and MAY move to `status/reviewed` after
  verification against the code. Only a human sets `status/canonical`.
- §9.5 `make vault-audit` MUST pass before vault changes are complete; the unit suite runs
  the same audit over the real vault.

Rationale: without a vault, decisions and hard-won constraints live only in commit messages
and chat sessions. The sibling repositories (anvil, darkharbour, wellspring) keep the same
kind of vault, and agents read it through the `vault` MCP server.

### Article X — Python Conventions

**Applicability**: Effective 2026-10-03. Applies to new and modified code under `ember/`
and `evals/` (full strictness). `tests/` is covered with one relaxation: §10.2 (one class
per file) does not apply to test-class groupings (e.g. `class TestIntentAndReadiness`) —
grouped test classes that share a fixture scope or scenario family MAY share a file.
`scripts/` is a collection of standalone entry points, not a package; §10.1 does not apply
(no `__init__.py` required). Existing violations are enumerated under §10.18 and MUST NOT
increase. These rules refine Article VIII; where they are silent, Article VIII governs. They
are adapted from the peer repositories' constitutions (anvil, wellspring, sonarqube-standalone,
darkfactory, infrastructure, k8s.platform) harvested on 2026-10-03.

- §10.1 **Package ownership via `__init__.py`.** Every fully-owned package level under
  `ember/` MUST carry an `__init__.py`. Sub-package markers are bare and docstring-only:
  no imports and no re-exports of symbols defined in sibling modules. The single exception
  is the package root `ember/__init__.py`: it MAY carry the module docstring, `__version__`,
  and re-exports of symbols that form the package's public API surface. No other
  `__init__.py` in the tree may re-export anything. A sub-package whose purpose is a named
  public API (e.g. `ember/agent_kit/`) puts that code in a normal named module inside the
  sub-package (e.g. `api.py`) and callers import from that module explicitly — not through
  the sub-package `__init__.py`. Data-only directories (no `.py` files) MUST NOT contain
  an `__init__.py`.
- §10.2 **One class per file.** A source file declares at most one primary class. A tightly
  coupled exception class raised only by that primary class MAY share its file.
- §10.3 **Sizing.** A module SHOULD NOT exceed 400 physical lines; reaching the ceiling is a
  design signal to split by responsibility — never delete docstrings, compress code, or
  suppress a check to comply. Evaluate decomposition when a package level reaches six peer
  modules, and keep nesting to at most two levels below the package root.
- §10.4 **Naming.** Modules are `snake_case.py`, named after their primary class when one
  exists. Classes are `PascalCase` with a subsystem suffix (`…Server`, `…Engine`, `…Client`,
  `…Error`). Constants are `UPPER_CASE`; private names start with `_`.
- §10.5 **Imports.** All imports live at the top of the file. Four exceptions only: a
  `TYPE_CHECKING` import that breaks a genuine runtime cycle, carrying a `# cycle:` comment; a
  `try`/`except ImportError` guard for an optional dependency, naming `ImportError`
  explicitly; an import of a module that ships outside this package and is loadable only after
  adjusting `sys.path` (the model snapshot's `joint_schema_model`), carrying an
  `# import-placement:allow` comment; and a last-resort `# import-placement:allow` with a
  justification. Internal `ember` modules MUST NOT be lazy-imported. Inside `ember/`, use
  relative imports; absolute `ember.` imports are valid only from outside the package
  (`tests/`, `scripts/`). Never import a symbol through an `__init__` re-export — import the
  defining module.
- §10.6 **Typing.** Article VIII's `mypy --strict` is the floor. A type suppression MUST carry
  a specific error code and a comment explaining why (`# type: ignore[arg-type]  - reason`);
  bare `# type: ignore`, `cast()` used to silence the checker, and `Any` used as an escape
  hatch are prohibited. Every module starts with `from __future__ import annotations`; never
  write string-literal forward references; prefer PEP 604 unions (`str | None`) over
  `typing.Optional`/`Dict`/`List`.
- §10.7 **Enums over magic strings.** A value drawn from a fixed, known set is an `Enum`
  (`StrEnum`/`IntEnum`), not a bare string constant or ad-hoc dict mapping. A Pydantic
  `Literal[...]` is permitted when the field is part of a published schema (for example the
  `advise` question `type`).
- §10.8 **Data models.** Structured data that crosses a boundary (HTTP, MCP, config, on-disk)
  uses a Pydantic v2 `BaseModel`; an internal value object that never crosses one MAY be a
  `@dataclass(frozen=True)` (for example the model registry's `ModelSpec`).
- §10.9 **Interfaces and dependencies.** Interfaces are `typing.Protocol`, never `abc.ABC`.
  Dependencies are constructor-injected. Service locators, and module-level singletons or
  mutable state used as general dependency plumbing, are prohibited. A private, module-owned
  lazy cache for a process-wide resource — the loaded engine (`server._ENGINE`) or the runtime
  module (`runtime._JOINT_MODULE`) — is permitted and is not public API. A test double replaces
  a boundary you own, never the unit under test.
- §10.10 **Docstrings.** Every module, class, and public function carries a NumPy-style
  docstring; a class documents its constructor parameters in `__init__`. One-line docstrings
  are acceptable only for trivial properties. Enforced by ruff `D` with
  `convention = "numpy"` over `ember/`; tests and scripts are exempt.
- §10.11 **Comments.** Comments explain why, not what. Section separators use solid `#` lines,
  never dashed rules. Every rule exception carries a machine-readable tag (`# cycle:`,
  `# import-placement:allow`, `# async-first:exception`).
- §10.12 **Error handling.** Raise typed exceptions; bare `except:` and swallowed errors are
  prohibited. Outbound network calls set an explicit timeout.
- §10.13 **Logging.** Library code logs through `logging.getLogger(__name__)` and never calls
  `print`; entry points render user output. In `mcp_server.py`, stdout remains the JSON-RPC
  wire (Additional Constraints).
- §10.14 **Concurrency.** Model inference is synchronous behind the engine lock and MUST NOT
  be made async. Async is used only at I/O boundaries and MUST use structured concurrency;
  fire-and-forget tasks are prohibited.
- §10.15 **Entry points, not a God class.** Each subsystem exposes one composition root
  (`Engine.advise`, `process.start`, `mcp_server.main`, `cli.main`). ember deliberately does
  not adopt a single application-wide façade (God Class): the MCP / HTTP / CLI split is the
  seam, and each root wires only its own subsystem.
- §10.16 **Client SDKs.** Any typed Python client for the model server follows a
  transport → sub-client → facade layering with one shared transport and lazy sub-clients; the
  server's request/response schema (`ember/serving/server.py`) remains the source of truth.
- §10.17 **Idempotent, atomic operations.** State-writing commands are safe to re-run and
  existence-guarded; a file write that could clobber another writes a sibling `.tmp` first and
  installs it with `os.replace()`.
- §10.18 **Migration debt.** Known existing violations, tracked here and never increased:
  modules over the 400-line ceiling that predate recording here: `ember/serving/runtime.py`
  (445, reduced from 507 on 2026-10-08 when Article V's redefinition removed
  `_classify_dir`/`skip_integrity` — still over the ceiling, but smaller; not yet paid down
  fully), `evals/agent/scenarios.py` (905, scenario data), `evals/analysis.py` (793),
  `evals/sections/sections_results.py` (506), `evals/charts/charts_calibration.py` (504),
  `evals/report_text.py` (447), `evals/metrics.py` (414), `evals/charts/charts.py` (412),
  `evals/eval/report_evals.py` (408); `ember/commands/lifecycle.py` defers
  `from ..serving import server` and `from ..mcp import mcp_server` inside the `serve` and
  `mcp` handlers (tagged `# import-placement:allow`) to avoid loading torch at CLI startup —
  this violates §10.5's "internal ember modules MUST NOT be lazy-imported" and stays tracked
  until those entry points no longer share a process with the CLI parser;
  `ember/mcp/mcp_types.py` declares two Pydantic models
  (`Question` and `AdviseInput`) — `Question` is a sub-schema field type of `AdviseInput`
  with no independent callers, satisfying the spirit of §10.2's tight-coupling principle
  though not the letter of the exception; `evals/render/blocks.py` declares 17 frozen
  dataclass types that
  form a single DSL for the report renderer — each type is a leaf value with no independent
  callers; splitting to 17 files adds ceremony with no readability gain;
  `scripts/vault_audit.py` declares four classes (`Rule`, `Finding`, `Frontmatter`,
  `VaultIndex`) that are tightly coupled steps in a single audit pipeline — splitting would
  require four separate files for a 201-line script; and most modules are function-oriented
  rather than one-class-per-file. NumPy docstrings (ruff `D`) and the
  `py.typed` marker are now enforced for `ember/`; `evals/` and `tests/` are exempt from
  ruff `D`. Each remaining item is paid down as its file is next touched. Previously
  tracked items now resolved: `ember/cli.py` (1086 lines, split into a 141-line composition
  root plus `ember/commands/`, every module under 400 lines, 2026-10-06); the `evals/`
  agent-condition and report-tone magic-string sets (`Condition` in
  `evals/agent/condition.py`, `Tone` in `evals/render/tone.py`, 2026-10-06);
  `ember/mcp/mcp_server.py` two-class violation (classes moved to `ember/mcp/mcp_types.py`
  on 2026-10-04); `evals/agent/opencode.py` two-class violation (`ToolCall` →
  `tool_call.py`, `Transcript` → `transcript.py`, 2026-10-04); `evals/agent/sandbox.py`
  two-class violation (`Snapshot` → `snapshot.py`, 2026-10-04); `ember/models.py` briefly at
  470 lines after the `specs/002-anaconda-models-provider/` feature added the `ModelSource`
  enum and a direct S3-compatible download path (recorded 2026-10-08), resolved the same day
  by splitting the download logic into `ember/cfg/anaconda_s3.py` — `ember/models.py` is now
  360 lines.

Rationale: ember's sibling repositories converge on these conventions, and adopting them keeps
agent-written changes consistent across the family. Where ember's runtime differs — synchronous
MPS inference, an MCP / HTTP / CLI seam, and deliberately function-oriented modules — the rule
is scoped or the divergence recorded, so this constitution stays truthful about what the code
actually does.

### Article XI — Test-Driven Development and Coverage Ratchet

**Applicability**: Effective 2026-10-04. Applies to all new features and non-trivial
changes across `ember/`, `evals/`, and `tests/`.

Tests MUST be written before or in the same commit as implementation. The Red-Green-Refactor
discipline is the default; tests that arrive after implementation in a separate commit are a
process violation and MUST be flagged at review.

- §11.1 **Test-first default.** Every new public function, class, or behaviour change ships
  with a corresponding test in the same commit. Agents MUST NOT mark a task complete without
  demonstrating test coverage for the changed path.
- §11.2 **Coverage ratchet.** The enforced floor (`fail_under` in
  `[tool.coverage.report]`) equals the current measured level and MAY only increase.
  Lowering it requires explicit human approval recorded in an amendment to this Article.
  The current floor is **81%**. Run `make test-cov` to see the current percentage before
  setting a new floor.
- §11.3 **No deleting tests to pass.** Removing a test to make coverage or a test run pass
  is a constitution violation. If a test is wrong, fix the test; do not delete it.
- §11.4 **End-to-end path.** At least one test MUST exercise each MCP→HTTP→Engine call
  path end-to-end (via stdio or HTTP fixture). Model-backed tests are exempt from CI but
  MUST exist and be runnable locally (`make test`).

Rationale: a codebase that will grow needs a discipline that prevents the accumulation of
untested paths. Ratcheting the floor makes it impossible for coverage to regress silently.

### Article XII — Async-First

**Applicability**: Effective 2026-10-04. Applies to all I/O-bound code in `ember/`.
The model inference path is the sole explicit exception.

All FastAPI route handlers and middleware MUST be declared `async def`. All outbound HTTP
calls (e.g. health probes in `process.py`) MUST use `httpx.AsyncClient` or equivalent
async transport when called from an async context; a synchronous call that must run from an
async context is offloaded with `anyio.to_thread.run_sync`. All file I/O on hot paths MUST use
`anyio.Path` or be offloaded the same way.

- §12.1 **Route handlers.** Every `@app.get`, `@app.post`, and `@app.middleware` function
  MUST be `async def`, except a handler covered by §12.2.
- §12.2 **Synchronous exception — engine lock.** `_ENGINE.advise()` is synchronous by
  design (Article X §10.14). A FastAPI handler that calls the engine MAY remain `def` (FastAPI
  runs it in its threadpool) or offload the call with `anyio.to_thread.run_sync`. A `def`
  handler MUST carry a `# async-first:exception - engine lock is synchronous` comment.
- §12.3 **MCP server.** MCP tool handlers are `async def`. The `advise` tool calls the HTTP
  layer with `httpx.AsyncClient` and offloads the synchronous lifecycle check
  (`process.start` / `process.is_up`) with `anyio.to_thread.run_sync`. Any new MCP tool that
  performs I/O MUST follow the same pattern.
- §12.4 **Tags.** Pure computation and synchronous code in sync-only entry points (the CLI,
  `process` lifecycle helpers called from the CLI) need no tag. A synchronous function that
  performs I/O and is reached from an async context — directly, as a route handler, or through
  a worker thread — MUST carry `# async-first:exception - <reason>`. Synchronous I/O called
  from an async context without that tag is a violation.

Rationale: the server runs under uvicorn's async event loop. Sync handlers block the loop
and serialize requests. Async handlers let uvicorn interleave health probes and metrics
reads during the engine lock wait.

### Article XIII — Layered Architecture

**Applicability**: Effective 2026-10-04. Applies to `ember/` and any future layers.

ember's architecture is a strict three-layer stack. Primitives from an inner layer MUST NOT
leak into an outer layer; outer layers call inward through defined interfaces only.

```
MCP layer        (ember/mcp/)                     ← agent-facing; no model primitives
HTTP layer       (ember/serving/server.py,        ← REST API + lifecycle; no MCP concepts
                  ember/serving/process.py)
Engine layer     (ember/serving/runtime.py,       ← model I/O; no HTTP/MCP concepts
                  media.py, hosted.py)
Shared           (ember/cfg/, ember/models.py)    ← configuration and model registry
```

- §13.1 **MCP layer** (`ember/mcp/`). Handles the MCP stdio protocol: parses tool inputs,
  calls the HTTP layer over `httpx`, raises `ToolError`. It MUST NOT import torch, load
  the model, or reference `Engine`. It MAY import `ember/serving/process.py` for lazy
  autostart (that module imports neither torch nor FastAPI), plus `ember/cfg/` and
  `ember/agent_kit/`. It MUST NOT parse or validate model outputs beyond what
  the MCP schema requires.
- §13.2 **HTTP layer** (`ember/serving/server.py`, `ember/serving/process.py`). Exposes the
  REST API and lifecycle. It MUST NOT import from `ember/mcp/`. It MAY import `Engine`
  directly and MUST own all Prometheus metrics.
- §13.3 **Engine layer** (`ember/serving/runtime.py`). Loads the model, runs inference,
  returns structured dicts. It MUST NOT import FastAPI, httpx, MCP, or any
  network/protocol library.
- §13.4 **Cross-layer data contracts.** Data crossing a layer boundary MUST be a Pydantic
  `BaseModel` or a plain `dict[str, Any]` (for JSON pass-through). No torch tensors,
  processor objects, or internal runtime state may cross a layer boundary.
- §13.5 **Configuration.** All layers read configuration through `ember/cfg/`
  (`config.resolve()`; the client endpoint through `endpoint.Endpoint.resolve()`). Default
  host, port, URL, and device values live only in `ember/cfg/config.py`; no other module
  hard-codes them.

Rationale: strict layering makes each layer independently testable and replaceable. The
MCP layer can be tested without a running model server; the HTTP layer can be tested with a
fake engine; the engine can be tested directly.

### Article XIV — Pit of Success

**Applicability**: Effective 2026-10-04. Applies to the install, configuration, and
runtime paths.

The default path — `uv tool install ember-advise`, `ember doctor`, `ember start` — MUST always
produce a working system on supported hardware without manual intervention. Optional or
enhanced capabilities MUST silently degrade, never crash or block.

- §14.1 **Install layer.** Model weights are downloaded on explicit user request
  (`ember model pull`, `make download`). The tool installs without weights present. The
  lifecycle path (`ember start`, MCP autostart, `process.start`) refuses to launch a server
  for a model that is not pulled and prints an actionable message naming
  `ember model pull`; a server process that comes up without a loadable model stays up and
  answers `503` on `POST /v1/systemone`. Neither path ends in a traceback.
- §14.2 **Device fallback.** `EMBER_DEVICE=auto` is the default; it selects MPS or CUDA when
  available and CPU otherwise. CPU is the always-available fallback on every platform the
  server runs on; supported platforms remain those of Article VI.
- §14.3 **Graceful 503.** When the model has not finished loading, `POST /v1/systemone`
  returns `503 Service Unavailable` with an actionable message. The MCP layer surfaces this
  as a `ToolError` the agent can read and retry.
- §14.4 **No crash on optional missing deps.** Doctor, status, and lifecycle commands MUST
  NOT crash when optional dependencies (torch, transformers) are absent. They report the
  missing dep and continue.
- §14.5 **Idempotent setup.** `make bootstrap` and `ember init` are safe to re-run. They
  detect existing state and skip steps that are already complete.

Rationale: agents and users must be able to onboard, restart, and recover from a single
actionable message instead of a traceback or a documentation hunt. Pit-of-success design
makes the happy path the easiest path.

### Article XV — Simplicity First and YAGNI

**Applicability**: Effective 2026-10-04. Applies to all code, dependency, and architecture
decisions across the repository.

Every change MUST favour the simplest, most boring solution that fully satisfies the stated
requirement. Complexity is never the default; it MUST be justified by a concrete, present
requirement.

- §15.1 **Simplest viable solution.** Before choosing an implementation, identify the
  simplest approach that meets the requirement. If a more complex approach is chosen, the
  reason MUST be documented in the vault or the commit message.
- §15.2 **Boring over novel.** Prefer mature, well-understood libraries and patterns.
  A novel or experimental dependency MUST NOT be introduced unless a simpler proven
  alternative has been explicitly considered and rejected. New dependencies MUST be
  justified in the commit or a vault decision note.
- §15.3 **YAGNI.** Build only what the current requirement needs. Speculative generality,
  premature abstraction, unused configuration knobs, and "future-proofing" for unrequested
  scenarios are forbidden. Introduce an abstraction only when the second concrete use case
  arrives.
- §15.4 **Reuse first.** Existing utilities, patterns, and abstractions already in the
  codebase MUST be reused before a new one is introduced. Adding a second way to do
  something the codebase already does is reject-worthy.
- §15.5 **Testability gate.** An approach that cannot be demonstrated correct through tests
  MUST NOT be shipped as the chosen solution. A simpler, demonstrably testable approach
  is always preferred. This pairs with Article XI.

Rationale: ember is a focused tool. Complexity accumulates silently; YAGNI and simplicity-
first discipline are the primary defences against it. Agents making implementation choices
MUST apply §15.1–§15.4 before selecting a design and MUST NOT add complexity that is not
required by the current work.

## Additional Constraints

- The product name is **ember**, after the Ember mascot, in every artifact: package `ember`,
  MCP server `ember` with the `advise` tool, skill `ember-advise`, resource `ember://guide`,
  environment variables `EMBER_*`, and repository `shapeandshare/ember`. The one exception
  is the distribution, `ember-advise`, because `ember` is taken on PyPI and `gut` is held
  by an empty project there. "Gut feeling" phrasing, such
  as the tagline, is flavor text, not a name. "Clef" MUST refer only to Cloudflare's
  upstream model. ember advises; agents decide.
- Python 3.12 managed by uv (consumers install with `uv tool install --python 3.12`); console
  scripts `ember`, `gut`, `ember-advise`, and `ember-mcp` are the supported entry points.
- `stdout` of the MCP process is the JSON-RPC wire; diagnostics MUST go to stderr.
- Per-machine generated files (`opencode.json`, `.opencode/plugins/ember.js`,
  `.opencode/skills/ember-advise/`) MUST NOT be committed.
- Repository code is MIT-licensed; the upstream Clef weights and `joint_schema_model.py` remain
  Apache-2.0 and are downloaded at runtime, never vendored.

## Development Workflow & Quality Gates

1. Plan non-trivial features with spec-kit (`/speckit.specify` → `/speckit.plan` →
   `/speckit.tasks` → `/speckit.implement`); every plan MUST pass a Constitution Check.
2. Commit atomically with Conventional Commits subjects; **tests land in the same commit as
   the code they cover** (Article XI). No implementation commit is complete without its tests.
3. Gate every commit on `make check`; gate PRs on `make pr-ready`; gate merges on CI plus
   `make test` for model-affecting changes, run on a maintainer's Apple Silicon machine
   (`make test-strict` fails instead of skipping when weights are missing).
4. Keep `AGENTS.md`, `README.md`, and the agent kit consistent with each other and with this
   constitution in the same change.
5. Before choosing an implementation, verify it is the simplest viable solution (Article XV
   §15.1). If a more complex approach is chosen, document why in the commit or vault.
6. New FastAPI routes MUST be `async def` (Article XII §12.1). Any sync handler that calls
   the engine carries a `# async-first:exception - engine lock is synchronous` comment.

## Governance

- This constitution supersedes ad hoc practice for all work in this repository. `AGENTS.md`
  operationalizes it for agent sessions; where the two conflict, the constitution wins and
  `AGENTS.md` MUST be updated.
- Agents MUST NOT weaken a principle to make work pass; principle changes are human-approved
  amendments.
- Amendments land through a pull request that prepends a new Sync Impact Report block at the
  top of this file and bumps the version: MAJOR for removing or redefining a principle, MINOR
  for adding a principle or section, PATCH for clarifications.
- Reviews MUST check changes against the Articles, with special attention to Article III
  (agent contract) and Article V (model loading).

**Version**: 3.1.1 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-09
