---

description: "Task list for Anaconda Models as a First-Class Preferred Provider"
---

# Tasks: Anaconda Models as a First-Class Preferred Provider

> **Implementation status (2026-10-08, reconciled, then corrected)**: Implemented, including
> scope the user expanded mid-stream beyond this file's original plan — two Anaconda entries
> (`anaconda-flash` AND `anaconda-clef`, not just one), per-entry `s3_prefix` with a shared
> `anaconda_s3_bucket` config fallback (not per-entry `s3_bucket` sharing nothing — see the
> correction below), and a plain AWS S3 download path (see [research.md](./research.md)
> R3-addendum, R3-addendum-2, R3-addendum-3, R5). **Correction (2026-10-08, same day)**: the
> initial implementation pass (R3-addendum/R3-addendum-2) hypothesized Anaconda's internal
> model-catalog infrastructure over Cloudflare R2 (verified R2 account endpoint, per-entry
> `dev-model-catalog` bucket default); the maintainer corrected this directly — "we will not
> call R2 in this scenario, when running hosted we will have access to an s3 bucket will all
> of the files" — so the shipped design now targets a plain AWS S3 bucket (no custom
> `endpoint_url`, no R2 framing), with the bucket resolved from a new shared
> `anaconda_s3_bucket` config fallback rather than a per-entry R2-catalog default. See
> research.md R3-addendum-3 for the full correction. Checkboxes below are
> **ticked against verified, currently-passing tests** (confirmed by running
> `pytest -m "not model" -q`, all green, 2026-10-08), with an inline note on every task whose
> actual implementation diverged from its original text (e.g. T011's "one new ModelSpec
> entry" became two; T001's catalog-API assumption was superseded, twice, first by direct R2
> S3-compatible access and then corrected to plain AWS S3). Tasks genuinely not yet done (the
> unverified `s3_prefix` follow-up, the live-bucket end-to-end pull, and the real
> hosted-endpoint scenario) are left unchecked and called out explicitly, not silently implied
> by a blanket "done" banner. **For full narrative context**,
> [research.md](./research.md) (R1–R5) and the vault decision note
> `vault/decisions/2026-10-07-anaconda-models-as-preferred-provider.md` remain the
> authoritative record of what was discovered and why — this file's checkboxes now track
> actual test-verified completion, not just intent. All functional requirements (spec.md
> FR-001–FR-012) are satisfied at the hash-pinning/dispatch level; `make pr-ready` passes
> (388 tests, confirmed 2026-10-08); see `COMPATIBILITY.md` for the final registry entries
> shipped and its noted limitation (S3 prefix unverified against the live bucket).

**Input**: Design documents from `/specs/002-anaconda-models-provider/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required, not optional. Constitution Article XI (Test-Driven Development) mandates
a failing test before implementation for every behavior change in this repository — tests are
included in every phase below, written first (Red), confirmed failing, then made to pass
(Green).

**Organization**: Tasks are grouped by user story (spec.md US1–US3) to enable independent
implementation and testing of each. `make check` (compile + unit tests) MUST pass before any
task is marked complete (Article XI §11.1); `make pr-ready` MUST pass before this feature's PR.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on an incomplete task)
- **[Story]**: Maps the task to US1, US2, or US3 from spec.md
- File paths are exact, taken from plan.md's Project Structure and verified against the
  current tree (not guessed)

## Path Conventions

Single Python package at the repository root (`ember/`), matching plan.md's Structure
Decision: no new top-level module or service.

---

## Phase 1: Setup

**Purpose**: Pin the concrete registry values this feature needs before any code changes.
Per research.md R1/R3, the artifact itself (commit, schema hash, head hash) is already known
(identical to the existing `flash` entry); what remains is the Anaconda-catalog-specific
addressing, which needs a short verification spike before T004+ can be written correctly.

- [x] T001 Verify Anaconda catalog download addressing for the ingested Clef-flash
      collection (research.md R3): confirm whether the catalog is reachable through
      `huggingface_hub.snapshot_download` with an `HF_ENDPOINT` override, or requires a
      distinct download mechanism. Record the finding as a short addendum in
      `specs/002-anaconda-models-provider/research.md` (new `R3-addendum` subsection) citing
      the actual verified mechanism — do not proceed to T004 on an assumption.
      **Done, outcome differs from every anticipated option, twice**: neither HF-Hub-compatible
      nor the Metaflow-scoped `AnacondaModelClient`. The first verification pass concluded
      direct S3-compatible (Cloudflare R2) access against Anaconda's internal catalog
      (R3-addendum, R3-addendum-2); the maintainer then corrected this directly (R3-addendum-3,
      2026-10-08): it is a plain AWS S3 bucket made available when ember runs on Anaconda's
      hosted platform, already containing the full model files — not R2, not an internal
      catalog. See research.md R3-addendum through R3-addendum-3.
- [x] T002 [P] Decide and record the new registry key name (e.g. `anaconda-flash`) and
      `dir_name` (e.g. `anaconda-clef-flash`) for the Anaconda-catalog entry in
      `specs/002-anaconda-models-provider/data-model.md`, replacing the "exact key decided at
      `/speckit.tasks`" placeholder with the chosen values. Follow existing naming convention
      in `ember/models.py` (`ModelSpec.name`/`dir_name` are short, lowercase, hyphenated).
      **Done, scope expanded**: two keys decided, not one — `anaconda-flash`
      (`dir_name="anaconda-clef-flash"`) and `anaconda-clef` (`dir_name="anaconda-clef"`),
      per data-model.md "Initial Anaconda registry scope."
- [x] T003 [P] Confirm the exact pinned values to reuse for the new entry by reading
      `ember/models.py`'s existing `REGISTRY["flash"]` entry (`revision`,
      `schema_sha256`, `head_sha256`, `approx_bytes`, `params`) — record them in
      `specs/002-anaconda-models-provider/data-model.md` as the literal values the new entry
      will copy (per research R1: identical artifact, identical hashes).
      **Done for both entries**: `anaconda-flash` copies `flash`'s `revision`, `anaconda-clef`
      copies `full`'s (data-model.md table). The `schema_sha256`/`head_sha256` fields this
      task originally referenced no longer exist on `ModelSpec` — removed 2026-10-08 when
      constitution Article V was redefined ("Model Loading"); see
      `vault/decisions/2026-10-08-article-v-redefined-model-loading.md`. The tests that
      verified this (`test_registry_anaconda_flash_*`/`::test_registry_anaconda_clef_*`) were
      removed with them.

**Checkpoint**: The exact `ModelSpec` field values for the new entry are known and recorded
before any implementation task below is started.

---

## Phase 2: Foundational

No foundational/blocking infrastructure is required. Per plan.md's Constitution Check and
research.md R1/R2, this feature touches no shared infrastructure that multiple user stories
depend on beyond the registry entry itself, which is US1's first task. Proceed directly to
Phase 3.

---

## Phase 3: User Story 1 - Run an Anaconda decision model locally by default (Priority: P1) 🎯 MVP

**Goal**: An unconfigured ember install resolves, pulls, and serves the new Anaconda-catalog
registry entry by default, while an explicit Clef selection continues to work unchanged.

**Independent Test**: On a clean config (no `model` override via flag/env/config file), run
`ember model pull` and `ember doctor`; confirm the resolved and loaded model is the new
Anaconda entry, not `flash`. Separately, run `EMBER_MODEL=flash ember doctor` and confirm
`flash` is still reported and loadable.

### Tests for User Story 1 (write first, confirm failing, per Article XI)

- [x] T004 [P] [US1] In `tests/test_model_integrity.py`, add
      `test_registry_<new-key>_has_well_formed_schema_sha256`,
      `test_registry_<new-key>_has_well_formed_head_sha256`,
      `test_registry_<new-key>_schema_sha256_matches_pinned_value`, and
      `test_registry_<new-key>_head_sha256_matches_pinned_value`, mirroring the existing
      `flash`/`full` tests at lines 41–78, asserting the new entry's hashes equal the same
      pinned `SCHEMA_SHA256`/`HEAD_SHA256_FLASH` constants already defined in that file (per
      research R1 and T003: identical artifact, identical hashes). Run
      `pytest tests/test_model_integrity.py -k <new-key> -x` and confirm it FAILS (the entry
      does not exist yet).
      **Done at the time; since removed (2026-10-08)**: `test_registry_anaconda_flash_*`
      (4 tests) and `test_registry_anaconda_clef_*` (4 tests) in
      `tests/test_model_integrity.py` were added and passed. `ModelSpec.schema_sha256`/
      `head_sha256` no longer exist — removed the same day as a separate, repo-wide change
      when constitution Article V was redefined ("Model Loading"; see
      `vault/decisions/2026-10-08-article-v-redefined-model-loading.md`), and these hash
      tests were removed with them. `tests/test_model_integrity.py` now covers registry
      structure (`source`, `s3_bucket`/`s3_prefix`, `kind`) instead.
- [x] T005 [P] [US1] In `tests/test_model_integrity.py`, extend
      `test_all_registry_entries_are_decision_kind` (around line 85) and any
      `REGISTRY`-iterating assertion to cover the new entry automatically (it already iterates
      `REGISTRY.values()`, so no new test is needed there — verify by running it and confirm
      it still passes once T004's entry exists; if it does not auto-cover, add an explicit
      assertion for the new key). Confirm current behavior first by running
      `pytest tests/test_model_integrity.py -k all_registry_entries_are_decision_kind` before
      any implementation change.
      **Done**: auto-covered as predicted, confirmed passing with both new entries present —
      no explicit new assertion was needed, the expected "regression lock" outcome.
- [x] T006 [US1] In `tests/test_cli.py`, add a test that monkeypatches `config.resolve` (or
      clears `EMBER_MODEL`/the config file) to simulate "no model preference configured" and
      asserts `cli.main(["doctor"])` reports the new Anaconda key, not `"flash"`, as the
      selected model (mirrors the existing `test_doctor_treats_a_stopped_server_as_information`
      pattern at line 204). Run it and confirm it FAILS against current code (`DEFAULT` is
      still `"flash"`).
      **Done**: `test_doctor_defaults_to_the_anaconda_model_when_unconfigured` in
      `tests/test_cli.py:260`; passes.
- [x] T007 [US1] In `tests/test_cli.py`, add a test asserting
      `EMBER_MODEL=flash` (or an equivalent explicit override) still resolves to and reports
      `"flash"` via `ember doctor`, unaffected by the new default (spec FR-003, FR-011;
      contracts/model-registry.md rule 11). Run it and confirm it currently PASSES (this locks
      in the non-regression before the default changes).
      **Done**: `test_doctor_respects_explicit_flash_override` in `tests/test_cli.py:274`;
      passes.
- [x] T008 [US1] [P] In `tests/test_runtime_unit.py`, add a non-model-backed test asserting
      `runtime._classify_dir` and `runtime.joint_module` correctly resolve the new registry
      spec by directory name, mirroring the existing coverage for `flash` at lines 39 and
      316–324. Run it and confirm it FAILS (the new key does not exist in `REGISTRY` yet).
      **Done at the time; `_classify_dir` since removed (2026-10-08)**:
      `test_classify_dir_resolves_anaconda_flash_registry_spec` and
      `test_joint_module_resolves_anaconda_flash_dir` in `tests/test_runtime_unit.py` both
      passed. `runtime._classify_dir` no longer exists — it was deleted the same day as a
      separate, repo-wide change when constitution Article V was redefined ("Model Loading";
      see `vault/decisions/2026-10-08-article-v-redefined-model-loading.md`), and its test was
      removed with it. `test_joint_module_resolves_anaconda_flash_dir` still exists and still
      passes, updated to call `joint_module(anaconda_dir)` with no `spec=` argument.
- [x] T009 [US1] [P] In `tests/test_runtime_unit.py`, add a `@pytest.mark.model` test that
      loads the new Anaconda registry entry through the existing, unmodified
      `Engine`/`load_clef` (same pattern as any existing model-backed load test in that file)
      and asserts it produces a working `Engine` — this is the direct verification of research
      R2's "no loader change needed" claim. Skippable when weights are absent
      (`make test`/`make test-strict` semantics, Article XI §11.4).
      **Done**: `test_engine_loads_anaconda_flash_through_unmodified_loader` in
      `tests/test_runtime_unit.py`; `@pytest.mark.model`, skips when weights absent — not
      independently re-run on model-backed hardware during this reconciliation pass (see
      "Remaining verification" note at the end of Phase 3).

### Implementation for User Story 1

- [x] T010 [US1] In `tests/test_commands.py` (or `tests/test_model_integrity.py`), add a test
      asserting the new entry's pull path produces the same disk-space-check and
      download-failure error clarity as `flash` (spec FR-009): simulate low free disk space
      (mirroring any existing `_disk_ok`-triggered test pattern for `pull()`, or add one
      alongside it if none exists yet) and assert the resulting `RuntimeError` message is
      equally actionable (names the model, suggests `--allow-low-disk`) for the new key. If
      T011 (below) introduces a catalog-specific pull branch per T001's finding, this test
      MUST also exercise that branch's own disk-space/failure path, not just the HF-Hub
      fallback — do not let a custom branch bypass `_disk_ok()` untested. Run it and confirm
      it FAILS before the new entry exists.
      **Done, and extended beyond the original ask**: `test_pull_anaconda_flash_raises_...`,
      `test_download_anaconda_s3_raises_actionable_error_on_low_disk`, and
      `test_download_anaconda_s3_allow_low_disk_bypasses_check` in `tests/test_model_integrity.py`
      exercise the real `_download_anaconda_s3` body (not a mocked stand-in — an earlier,
      HIGH-severity test-quality gap, fixed per the inline comment at
      `tests/test_model_integrity.py:659-666`).
- [x] T011 [US1] In `ember/models.py`, add the new `ModelSpec` entry to `REGISTRY` using the
      values recorded in T002/T003 (name, repo/catalog identifier from T001's verified
      mechanism, `dir_name`, `params="9B"`, `approx_bytes=18 * 2**30`,
      `revision` identical to `REGISTRY["flash"].revision`, `schema_sha256` and `head_sha256`
      identical to `REGISTRY["flash"]`'s values, `kind="decision"`). If T001 found the catalog
      is not Hugging-Face-Hub-API-compatible, also add the minimal additive branch in
      `pull()`/`resolve_dir()`/`remove()` needed to download from the verified mechanism —
      scoped to only the new entry's source, per plan.md's "no loader change" constraint and
      contracts/model-registry.md rule 5. **If this branch needs to dispatch on which source
      a `ModelSpec` uses (Anaconda catalog vs. public Hugging Face Hub), that value is drawn
      from a fixed, known set and MUST be a `StrEnum` per constitution Article X §10.7 — never
      a bare string literal or boolean flag.** Keep the branch and any new enum minimal
      (Article XV); do not build a general multi-source plugin mechanism for two cases. Run
      T004, T005, T008, T010 and confirm they now PASS.
      **Done, scope expanded to two entries**: `anaconda-flash` AND `anaconda-clef` added to
      `REGISTRY`; `ModelSource` `StrEnum` added (`HUGGING_FACE`/`ANACONDA_S3`); AWS S3 download
      branch added (`_s3_client`, `_download_anaconda_s3`, later split into
      `ember/cfg/anaconda_s3.py`'s `s3_client()`/`download()`), dispatched in
      `pull()`/`resolve_dir()`/`remove()`. `ember/models.py` grew to 470 lines as a result —
      now tracked in constitution §10.18 (see this reconciliation's constitution amendment)
      and in plan.md's Complexity Tracking table, then resolved by the T032 split
      (360 lines). (Initial download design used R2-specific framing, corrected to plain AWS
      S3 per research.md R3-addendum-3.) T004/T005/T008/T010 all pass.
- [x] T012 [US1] In `ember/models.py`, change the module-level `DEFAULT` constant from
      `"flash"` to the new registry key (spec FR-002; data-model.md "Entity: DEFAULT"). Run
      T006 and confirm it now PASSES; re-run T007 and confirm it still PASSES (explicit
      override still wins, spec FR-003/FR-011).
      **Done**: `DEFAULT = "anaconda-flash"` (`ember/models.py:180`). T006/T007 both pass.
- [x] T013 [US1] In `ember/cfg/config.py`, update `DEFAULTS["model"]` (currently the literal
      string `"flash"` at line 16 — confirmed duplicated from `ember/models.py`'s `DEFAULT`,
      not derived from it) to the same new registry key, keeping the two defaults in sync.
      Add a short comment noting this value MUST match `ember.models.DEFAULT` (there is no
      automatic derivation today; a future refactor could import it directly, but per Article
      XV this task only fixes the immediate duplication-drift risk, it does not add new
      indirection). Run `make test-fast` and confirm no existing test asserting
      `cfg.DEFAULTS["model"] == "flash"` breaks (none found in the current suite — verify by
      searching `DEFAULTS\["model"\]` under `tests/` before editing).
      **Done**: `DEFAULTS["model"] = "anaconda-flash"` with the required sync-reminder comment
      present (`ember/cfg/config.py:16-20`). No test asserted the old literal; `make test-fast`
      is green. This hand-maintained duplication is a permanent, documented risk (vault
      decision note "Consequences"), not a defect — there is no automatic derivation path
      given Article XIII's layering rule (`cfg` cannot import `models`).
- [x] T014 [US1] Run `pytest tests/test_model_integrity.py tests/test_cli.py
      tests/test_runtime_unit.py tests/test_commands.py -m "not model"` and confirm all pass
      (Green). Then, on hardware with weights pulled for the new entry, run
      `pytest tests/test_runtime_unit.py -m model -k <new-key>` (T009) and confirm it passes.
      **Done (non-model portion)**: confirmed green on 2026-10-08
      (`pytest -m "not model" -q` — full suite, 388 tests, all pass). **Not done (model
      portion)**: the `-m model -k anaconda` run against real pulled weights was not executed
      during this reconciliation pass — no `anaconda-flash` weights are present on this
      machine. This remains a genuine open item, not silently assumed complete; see "Remaining
      verification" below.

**Remaining verification (not yet done, tracked explicitly rather than implied)**: T009's and
T014's model-backed assertions require real `anaconda-flash` weights pulled from the hosted
AWS S3 bucket, which itself depends on the unverified `s3_prefix` (see F5 in the
`/speckit.analyze` report and `research.md` R3-addendum-2/R3-addendum-3) actually working
end-to-end. Run `ember model pull anaconda-flash` on real hardware with real credentials and
`EMBER_ANACONDA_S3_BUCKET` set, then `pytest tests/test_runtime_unit.py -m model -k
anaconda_flash`, before considering Phase 3 fully closed.

**Checkpoint**: User Story 1 is fully functional — an unconfigured install defaults to the
Anaconda entry; an explicit `flash`/`full` selection is unaffected. This is the MVP: stop here
and validate with quickstart.md Scenarios 1–2 before continuing.

---

## Phase 4: User Story 2 - Choose any supported Anaconda model explicitly (Priority: P1)

**Goal**: A user can list, pull, select, and remove the Anaconda entry using the exact same
commands already used for Clef entries, with correct error messages for unknown names.

**Independent Test**: `ember model list` shows the Anaconda entry with correct metadata;
`ember model pull <new-key>` / `EMBER_MODEL=<new-key> ember start` / `ember model rm <new-key>`
all behave like their `flash` equivalents; an unknown name produces the existing clear error
listing valid names including the new key.

### Tests for User Story 2 (write first, confirm failing, per Article XI)

- [x] T015 [P] [US2] In `tests/test_commands.py`, extend the `cmd_model_list` test (around
      line 112, currently monkeypatching `list_models` to return a single `flash` row) with a
      second test asserting a real (non-monkeypatched) call to `models_mod.list_models()`
      includes a row for the new key with the correct `name`/`repo`/`params`/`kind` fields
      (contracts/model-registry.md rule 4). Confirm it FAILS before T011 lands if run against
      pre-T011 code, or confirm it already passes post-Phase-3 if run after (this task may
      overlap with Phase 3's completion — run it now to lock in coverage either way).
      **Done for both entries**: `test_model_list_real_call_includes_anaconda_flash` and
      `test_model_list_real_call_includes_anaconda_clef` in `tests/test_commands.py`; pass.
- [x] T016 [P] [US2] In `tests/test_commands.py`, mirror the existing `cmd_model_pull`
      (line 107), `cmd_model_path` (lines 118–125), and `cmd_model_rm` (lines 131–138) tests
      with parametrized or duplicated variants using the new key instead of `"flash"`,
      asserting identical return codes and output shape (contracts/model-registry.md rules
      5–7). Run and confirm they FAIL only if the new key is not yet registered; otherwise
      confirm they pass as a regression lock.
      **Done**: parametrized over `["flash", "anaconda-flash", "anaconda-clef"]` in
      `tests/test_commands.py`; passes for all three.
- [x] T017 [US2] In `tests/test_commands.py` or `tests/test_cli.py`, add a test asserting that
      pulling/starting/removing an unregistered model name still produces the existing clear
      error message, and that the message's list of valid names includes the new Anaconda key
      (spec FR-004 acceptance scenario 3; contracts/model-registry.md rule 9). Run and confirm
      it passes once T011 lands (the error-listing code already iterates `REGISTRY`
      generically, per plan.md's "no change expected" note — this test exists to prove that,
      not to drive new code).
      **Done**: `test_model_pull_unknown_name_lists_anaconda_flash_as_a_valid_choice` in
      `tests/test_commands.py`; confirms both `anaconda-flash` and `anaconda-clef` appear in
      the error's valid-choices list. Passed as a regression lock, as predicted — no new code
      was needed in the error-listing path.

### Implementation for User Story 2

- [x] T018 [US2] Run `ember/commands/models.py`'s existing `cmd_model_pull`/`cmd_model_list`/
      `cmd_model_path`/`cmd_model_rm` against the new registry key manually
      (`ember model list`, `ember model pull <new-key>`, `ember model path <new-key>`,
      `ember model rm <new-key>`) to confirm the "no change expected" conclusion in plan.md
      holds. If any command fails to treat the new entry identically to `flash` (for example
      because T011's catalog-specific pull branch needs wiring into `cmd_model_pull`), make
      the minimal fix in `ember/commands/models.py` needed to satisfy
      contracts/model-registry.md rules 4–7 — do not add new flags or subcommands (Article
      XV). Run T015–T017 and confirm all PASS.
      **Done, "no change expected" confirmed true**: `ember/commands/models.py` required no
      edits — the dispatch lives entirely in `ember/models.py` (T011). T015–T017 all pass.
      Manual `ember model list`/`pull`/`path`/`rm anaconda-flash` end-to-end runs against the
      live bucket were **not** exercised during this reconciliation (blocked on the same
      unverified `s3_prefix` as Phase 3's "Remaining verification" note) — only the
      test-suite-level (mocked S3) behavior is confirmed.

**Checkpoint**: User Stories 1 AND 2 both work independently. Validate with quickstart.md
Scenarios 3–4.

---

## Phase 5: User Story 3 - Use Anaconda-hosted models when running on Anaconda's platform (Priority: P2)

**Goal**: A user can point ember at an Anaconda-hosted decision-model endpoint using the
existing remote-endpoint configuration, with no new config surface, no auto-detection, and
clear observability of local-vs-remote status.

**Independent Test**: With `EMBER_SERVER_URL`/`EMBER_AUTH_TOKEN` set to an issued
Anaconda-hosted endpoint and no local model pulled, `advise` calls succeed end-to-end and
`ember doctor` clearly reports the remote endpoint is in use. With no endpoint configured,
behavior is unchanged from local-only operation.

### Tests for User Story 3 (write first, confirm failing only where behavior is new)

- [x] T019 [P] [US3] In `tests/test_cli.py` or `tests/test_endpoint.py` (whichever already
      covers `ember doctor`'s endpoint reporting, per
      `specs/001-remote-inference-servers/`), add a test confirming `ember doctor`'s existing
      endpoint-status output, when `EMBER_SERVER_URL` is set to a non-loopback HTTPS URL,
      clearly labels it as remote/non-local (contracts/hosted-endpoint.md rule 7). Run it and
      confirm it PASSES against current code — this is a regression lock proving the existing
      001 feature already satisfies this feature's US3 observability requirement (spec
      FR-005, SC-004) with no new code, per plan.md's "no client-side code change" conclusion.
      **Done**: `test_doctor_labels_a_configured_anaconda_hosted_endpoint_as_remote` in
      `tests/test_cli.py:192`; passes as a regression lock, confirming the predicted "no new
      code needed" outcome.
- [x] T020 [P] [US3] Add or confirm an existing test (likely already present from
      `specs/001-remote-inference-servers/tests/test_endpoint.py` /
      `tests/test_mcp_tool.py`) proving ember never auto-starts a local server or falls back
      to local inference when a non-loopback `server_url` is configured and unreachable
      (contracts/hosted-endpoint.md rules 2 and 6; spec Clarification 5, FR-007). If no such
      test exists, add one in `tests/test_mcp_tool.py` mirroring the existing autostart-
      suppression coverage for remote endpoints. Run and confirm it PASSES (no new behavior
      needed — this proves the existing mechanism already satisfies US3).
      **Done**: `test_ensure_server_never_autostarts_for_a_non_loopback_endpoint` in
      `tests/test_mcp_tool.py:164` (already existed from `specs/001-remote-inference-servers/`,
      confirmed still passing and sufficient — no Anaconda-specific addition needed).
- [x] T021 [US3] Add a test confirming that with no `EMBER_SERVER_URL`/`EMBER_AUTH_TOKEN`
      configured, no outbound network call occurs beyond the explicit `ember model pull`
      path (spec SC-005) — likely already covered by existing local-default tests; if not,
      add a minimal assertion in `tests/test_cli.py` that an unconfigured `doctor` run makes
      no remote HTTP call (mock/patch `httpx` and assert no non-loopback request is attempted).
      **Done**: `test_doctor_makes_no_remote_http_call_when_unconfigured` in
      `tests/test_cli.py:217`; passes.

### Implementation for User Story 3

- [x] T022 [US3] If T019–T021 reveal any gap (e.g., `ember doctor`'s remote/local labeling is
      ambiguous, or an edge case in autostart suppression is untested), make the minimal fix
      in `ember/commands/doctor.py` / `ember/commands/endpoint.py` needed to close it. Per
      plan.md's Constitution Check and research R5, **no new code is expected**; this task
      exists only to close any gap the tests above surface, not to build new functionality.
      Run T019–T021 and confirm all PASS.
      **Done, no gap found**: T019–T021 all passed without any fix to
      `ember/commands/doctor.py`/`ember/commands/endpoint.py` — confirms research R5's "no
      client-side code change" conclusion exactly as predicted.

**Checkpoint**: All three user stories are independently functional. Validate with
quickstart.md Scenarios 5–6 (Scenario 5 requires a real issued Anaconda-hosted endpoint and
credential — run manually when available, not part of automated CI, per quickstart.md's
validation checklist).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and agent-kit updates that span all three user stories, per
plan.md's "Modules to change" table and research.md R6 (no kit number re-measurement needed;
prose framing only).

- [x] T023 [P] Update `README.md` lines 6–7 ("ember runs a decision model (currently
      Cloudflare's Clef-Flash)...") and line 40 ("'Clef' always refers to Cloudflare's
      upstream model, never to this product.") to additionally name Anaconda's catalog
      distribution as the default/preferred source for the same model, while keeping the
      existing Clef-naming constraint intact verbatim (constitution Additional Constraints:
      '"Clef" MUST refer only to Cloudflare's upstream model' — do not weaken this rule, only
      add the Anaconda-source framing alongside it).
      **Done**: README.md's hero paragraph names Anaconda's catalog as the preferred default
      source with Cloudflare's public repo as a supported alternative; the "Clef' always
      refers to Cloudflare's upstream model" sentence is preserved verbatim. Also updated:
      lines 43-48 (registry framing), 157/208/221-223 (CLI/env-var tables) with the
      `anaconda-flash`/`anaconda-clef`/`EMBER_ANACONDA_S3_*` additions — beyond T023's
      originally-cited two line numbers, since the two-entry scope expansion (T002) touched
      more of the file than planned.
- [x] T024 [P] Add a new row to `COMPATIBILITY.md`'s "Tested models" table (after line 13) for
      the Anaconda-catalog entry, reusing the exact same Parameters/On disk/Modality/License/
      Pinned revision/Verified values already recorded for `Clef-Flash` (per research R6: same
      artifact, same measurements) — only the Registry key and a note on distribution source
      differ.
      **Done for both entries**: `COMPATIBILITY.md:12` (`anaconda-flash`) and `:14`
      (`anaconda-clef`), each explicitly noting "S3 pull path/prefix not yet exercised
      end-to-end" — the F5/unverified-prefix limitation is surfaced here, not hidden. Updated
      again same day (R3-addendum-3 correction) to describe the source as "AWS S3
      (Anaconda's hosted platform)" rather than "Anaconda model catalog (Cloudflare R2)".
- [x] T025 Update `ember/agent_kit/instructions.md` only if a model source is named in its
      text (currently it says "currently Cloudflare's Clef-Flash, local by default" — see line
      1). Any edit MUST keep the file at or under 2048 bytes (constitution §3.2; current size
      is 1978 bytes, leaving only ~70 bytes of headroom) — verify with
      `wc -c ember/agent_kit/instructions.md` after editing and revert/trim if it exceeds the
      cap. Run `pytest tests/test_agent_kit.py -k instructions` and confirm it still passes.
      **Done, no edit needed**: `instructions.md`'s shipped text does not name a specific model
      source (generic "a decision model... locally by default" framing), so the condition that
      would have triggered an edit did not apply. Confirmed still 1955 bytes (under the 2048
      cap) and `pytest tests/test_agent_kit.py -k instructions` passes.
- [x] T026 [P] Run `pytest tests/test_agent_kit.py` in full and confirm no other kit
      consistency check (skill frontmatter, guide resource) broke from T023–T025's prose
      changes.
      **Done**: full `tests/test_agent_kit.py` run (7 tests) passes, confirmed 2026-10-08.
- [x] T027 Run `make pr-ready` (format, lint, typecheck, security, compile, unit tests) and
      fix any violation before considering this feature complete (constitution Article VIII,
      Development Workflow gate 3).
      **Done, independently re-verified during this reconciliation (2026-10-08)**:
      `ruff format --check` (35 files formatted), `ruff check` (all checks passed), `mypy
      --strict` (no issues, 32 source files), `bandit -r ember/` (0 High/Medium findings, 2
      pre-existing Low findings unrelated to this feature), `pytest -m "not model"` (388 tests,
      all pass).
- [x] T028 Run `make test-cov` and confirm the coverage floor (currently 81%, Article XI
      §11.2) is still met or exceeded; do not lower `fail_under` to pass.
      **Done, independently re-verified (2026-10-08)**: measured 90.75% (well above the 81%
      floor); `fail_under` unchanged in `pyproject.toml`.
- [x] T029 Execute `specs/002-anaconda-models-provider/quickstart.md` Scenarios 1–4 and 6 by
      hand (Scenario 5 requires an issued Anaconda-hosted endpoint, run separately when
      available) and check off its validation checklist.
      **Done for Scenarios 1–4 and 6**: quickstart.md's own validation checklist shows these
      checked off with verification notes. **Scenario 5 remains explicitly unchecked** in
      quickstart.md (correctly — it requires a real issued Anaconda-hosted endpoint and
      credential not available in this environment) — this is the expected, documented
      incompleteness, not an oversight.
- [x] T030 Add a vault decision note under `vault/decisions/` (per constitution Article IX
      §9.2, `vault/_meta/templates/decision.md`) recording: the choice to ship the Anaconda
      entry as Anaconda's catalog distribution of the existing Clef/Clef-flash artifact rather
      than waiting for a novel Anaconda-trained model (research R1), and the "no loader
      change" / "no new provider abstraction" decision (research R2), linking the hub
      `vault/ember.md`. Start at `status/draft`.
      **Done**: `vault/decisions/2026-10-07-anaconda-models-as-preferred-provider.md`, linked
      from `vault/ember.md:44`, `status/draft`. Covers R1/R2 as specified plus the
      R3-addendum/R3-addendum-2/R5 findings that emerged after this task was originally
      planned.

### Phase 6 follow-up (new, added during `/speckit.analyze` remediation, 2026-10-08)

- [ ] T031 [NEW, BLOCKED, REVISED] Correct or verify `s3_prefix` on the `anaconda-flash`/
      `anaconda-clef` `REGISTRY` entries against the real hosted AWS S3 bucket, once that
      bucket and real credentials are available to verify against (research.md
      R3-addendum-3; spec FR-008). **Revised 2026-10-08**: this task originally named
      AISAGE-565's Anaconda-internal-catalog raw-snapshot ingestion path as the blocking
      dependency (R3-addendum-2) — that framing is now obsolete per the maintainer's
      correction (R3-addendum-3): the real dependency is simply having real
      `EMBER_ANACONDA_S3_ACCESS_KEY_ID`/`_SECRET_ACCESS_KEY`/`_BUCKET` values for the actual
      hosted-platform S3 bucket and confirming the object-key layout within it, independent
      of any Anaconda-internal catalog/ingestion pipeline. Until this is verified,
      `ember model pull anaconda-flash`/`anaconda-clef` is expected to fail against the real
      bucket with a clear "no objects found under s3://.../" `RuntimeError` (already tested:
      `test_download_anaconda_s3_raises_when_no_objects_found`) rather than silently
      succeeding with wrong data — this is the intended fail-closed behavior, not a bug to
      hide, but the prefix itself remains a tracked gap, not a completed item.
      **Confirmed still blocked (2026-10-08, re-checked during `/speckit.implement`)**: no
      `EMBER_ANACONDA_S3_*` credentials are configured in this environment, and no real hosted
      S3 bucket is reachable to verify the prefix against. This task genuinely cannot be
      completed from this environment — it requires both real credentials and a real bucket
      with real objects at a verified key layout, neither of which exist here. Left unchecked
      deliberately; do not mark complete without actually exercising
      `ember model pull anaconda-flash` against the real bucket and confirming the files
      land correctly.
- [x] T032 [NEW] Address `ember/models.py`'s Article X §10.3 sizing ceiling violation (470
      lines, over the 400-line limit) introduced by this feature's `ModelSource`/S3-download
      addition: either (a) add it to constitution `§10.18` migration debt (done separately as
      part of this `/speckit.analyze` remediation — see the constitution amendment), or (b)
      split the S3-compatible download logic into its own module (e.g.
      `ember/models_s3.py`) as a future follow-up. Not blocking this feature's merge since
      (a) is already satisfied, but tracked here so (b) is not forgotten.
      **Done (option b), 2026-10-08**: split `_s3_client`/`_download_anaconda_s3` out of
      `ember/models.py` into a new module `ember/cfg/anaconda_s3.py` (`s3_client()`/
      `download()`), matching the existing precedent that `ember/cfg/paths.py` already owns
      `anaconda_s3_cache()` — this is a config/shared-layer concern (credentials, connection),
      not registry logic. `ember/models.py` is now 360 lines (under the ceiling); the new
      module is 150 lines with 100% test coverage. `pull()`'s `ANACONDA_S3` branch now calls
      `anaconda_s3.download(spec, dest, _disk_ok(dest, spec.approx_bytes), allow_low_disk=...)`.
      A `TYPE_CHECKING`-guarded import (tagged `# cycle:`) avoids a runtime circular import
      between `ember.cfg` and `ember.models`, per Article X §10.5. All affected tests in
      `tests/test_model_integrity.py` updated to reference `ember.cfg.anaconda_s3` instead of
      the removed `models._s3_client`/`models._download_anaconda_s3` private functions.
      `make pr-ready` reconfirmed green (format, lint, mypy --strict, bandit, compile, 388
      tests) after the split. The constitution §10.18 entry added for this debt in the prior
      `/speckit.analyze` pass is now removed (debt paid down in the same feature it was
      recorded in) — see the corresponding constitution amendment.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately. T001 blocks T011 (cannot write the
  real pull implementation without knowing the verified download mechanism). T002/T003 block
  T004/T010/T011 (need the concrete field values before writing tests or code against them).
- **Foundational (Phase 2)**: Empty — no blocking infrastructure for this feature.
- **User Story 1 (Phase 3)**: Depends on Phase 1 completion. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Phase 1 and on US1's T011 (the registry entry must
  exist before its list/pull/path/rm behavior can be tested) — in practice, implement
  sequentially after US1, not in parallel, despite both being P1.
- **User Story 3 (Phase 5)**: Depends on Phase 1 only — it exercises the *existing*
  remote-endpoint mechanism and does not require the new registry entry to exist. Can be
  implemented in parallel with US1/US2 by a different contributor, per spec's P2 priority.
- **Polish (Phase 6)**: Depends on US1 and US2 for the documentation tasks (T023/T024 describe
  the shipped default); T025/T026 depend on T023. T027–T030 depend on all prior phases.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 1. No dependency on US2/US3. This is the MVP.
- **User Story 2 (P1)**: Can start after Phase 1, but its tests/implementation assume US1's
  registry entry (T011) exists — sequence after US1 in practice even though both are P1.
- **User Story 3 (P2)**: Can start after Phase 1, independently of US1/US2 — it tests/confirms
  the already-shipped remote-endpoint mechanism, unrelated to the new registry entry.

### Within Each User Story

- Tests are written and confirmed failing (or confirmed passing as a regression lock, where
  the task notes the behavior already exists) before implementation, per Article XI.
- Registry/data changes (T010, T011, T012, T013) before CLI-surface verification (T018).
- Story complete and `make check`-green before moving to the next phase.

### Parallel Opportunities

- T002 and T003 can run in parallel (different concerns: naming vs. pinned values) once T001
  completes.
- T004, T005, T008, T009 (different test files/functions) can run in parallel once T002/T003
  values are recorded.
- US3 (Phase 5) can be worked on in parallel with US1/US2 (Phase 3/4) by a different
  contributor, since it has no dependency on the new registry entry.
- T023 and T024 (different doc files) can run in parallel; T026 depends on T025.

---

## Parallel Example: User Story 1

```bash
# After T002/T003 record the concrete field values, launch these together:
Task: "Add registry integrity tests for the new key in tests/test_model_integrity.py (T004)"
Task: "Add runtime resolution tests for the new key in tests/test_runtime_unit.py (T008)"
Task: "Add model-backed Engine load test for the new key in tests/test_runtime_unit.py (T009)"
```

## Parallel Example: Cross-Story

```bash
# US3 has no dependency on the new registry entry and can run alongside US1/US2:
Task: "US1: add new ModelSpec entry to ember/models.py (T011)"
Task: "US3: add/confirm doctor remote-endpoint labeling test (T019)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003) — pins the concrete values research left open.
2. Phase 2: Foundational is empty — skip directly to Phase 3.
3. Complete Phase 3: User Story 1 (T004–T014).
4. **STOP and VALIDATE**: run quickstart.md Scenarios 1–2 independently.
5. This is a working, demonstrable default-model change.

### Incremental Delivery

1. Setup → Phase 3 (US1) → validate → this is the MVP (new default works, old explicit
   selection unaffected).
2. Add Phase 4 (US2) → validate → full registry parity (list/pull/select/remove) confirmed.
3. Add Phase 5 (US3) → validate → hosted-endpoint path confirmed (can be done in parallel with
   steps 1–2 by a separate contributor, since it has no shared-code dependency).
4. Phase 6 (Polish) → documentation, vault note, and final gates (`make pr-ready`,
   `make test-cov`).

### Parallel Team Strategy

With two contributors:

1. Contributor A completes Phase 1 (Setup) alone — it is small and blocks US1/US2.
2. Once Phase 1 lands:
   - Contributor A: Phase 3 (US1) → Phase 4 (US2), sequentially (US2 depends on US1's entry).
   - Contributor B: Phase 5 (US3), independently (no shared dependency).
3. Both converge on Phase 6 (Polish) once their stories are done.

---

## Notes

- [P] tasks touch different files or independent concerns within the same file and have no
  completed-task dependency blocking them.
- Every implementation task above is traceable to a specific functional requirement (spec.md
  FR-00x) or contract rule (contracts/model-registry.md, contracts/hosted-endpoint.md rule N),
  cited inline — this is not a template with placeholders. FR-012 ("no migration path,
  legacy-mode flag, deprecation period, or user-facing change notice is required") is a
  negative/non-functional requirement with nothing to build or test and intentionally has no
  task — its only effect is what this task list already does not contain (no T0xx task adds
  a migration notice, banner, or compatibility shim for the default-model change).
- Per research.md R1/R2/R5, most of this feature's "implementation" is additive registry data
  plus proof-by-test that already-shipped generic code paths (CLI commands, doctor, the
  remote-endpoint client) correctly treat the new entry/endpoint the same as existing ones —
  several tasks (T005, T015, T017, T019, T020, T021) are expected to pass as regression locks
  rather than drive new code, and that is the correct, YAGNI-respecting outcome, not a sign of
  missing tasks.
- Commit after each task or logical group, with Conventional Commits subjects scoped `ember`
  (constitution Additional Constraints / AGENTS.md commit scope table).
- `make check` MUST pass before any task is marked complete; `make pr-ready` MUST pass before
  the feature's PR (Article XI, Development Workflow gate 3).
