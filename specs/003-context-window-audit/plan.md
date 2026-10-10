# Implementation Plan: Context Window Audit — Explicit, Measured Length Limits

**Branch**: `003-context-window-audit` | **Date**: 2026-10-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-context-window-audit/spec.md`

## Summary

This feature makes every length limit explicit, exact, and measured.

- **Exact counting.** The server counts each request exactly as the model will encode it.
  It calls upstream `encode_record` with no truncation and splits the total into state,
  media, and fixed overhead.
- **Refusal, never truncation.** A request over the enforced limit (the lower of the
  per-request cap and the effective maximum) gets an actionable 413. The message names the
  governing setting and gives the split.
- **Runtime guard.** A served request's `usage.input_tokens` must equal its counted total.
  This keeps the no-truncation guarantee for unpinned model code too.
- **Visible limits.** Limits and their sources appear in the load log, in `/health`, and
  in `ember doctor` (live, configured, or unknown).
- **Measured caps.** A resumable long-context probe (`ember eval context`,
  `make eval-context`) pads 232 benchmark items with neutral public-domain filler to
  2K–64K tokens. It runs three evidence depths on flash and full, in separate worker
  processes, and records accuracy, Brier score, ECE, peak memory, and latency.
- **Pre-declared rule.** A rule fixed before the run picks each registered model's default
  cap. A decision note citing the snapshotted run supersedes D-002.

## Technical Context

**Language/Version**: Python 3.12 (uv)

**Primary Dependencies**:
- torch 2.14 (MPS), transformers 5.18
- FastAPI and uvicorn, mcp 2.3, Pydantic v2, httpx, prometheus-client, huggingface-hub
- upstream `joint_schema_model.py`, identical at flash `17f0b0ad` and full `2f3de3dd`

No new dependencies.

**Storage**: Files only:
- the registry, in code (`ModelSpec.max_request_length`)
- the JSON config
- probe artifacts: JSON and JSONL under `results/context/`, with snapshots in
  `evals/context/runs/`
- a vendored filler text, pinned by SHA-256

**Testing**: pytest and pytest-cov.
- Unit tests use fakes for the joint module and the processor.
- Tests marked `@pytest.mark.model` run locally only (`make test`, `make test-strict`).
- The probe is an eval, not a test, and is never in CI.

**Target Platform**: macOS on Apple Silicon (MPS, fp16) for both the server and the
probe. Counting and refusal behave the same on CUDA and CPU, but the probe measures MPS
only.

**Project Type**: A Python package (CLI, local HTTP model server, MCP stdio server) plus
an eval harness that runs only from a checkout.

**Performance Goals**: The spec sets no budget.
- **Size check**: the latency it adds to a warm short text request is measured and
  recorded. The informational target is 5% or less.
- **Probe compute**: bounded by a memory gate at each length, an exploratory subset for
  lengths after the first failure, and resumable rows.

**Constraints**:
- The refusal message has no `/` or `\`, because the MCP layer redacts paths.
- `instructions.md` stays at or under 2,048 bytes; 93 bytes are free today.
- Doctor and the MCP layer never import torch.
- The probe runs offline, using the vendored filler.
- `ember/serving/runtime.py` drops below 400 lines (Article X debt).

**Scale/Scope**: Up to 7 lengths × 3 depths × 2 models × 232 items, about 9,700
inferences, many of them long. That is hours to days on the reference M4 Max; the run can
be resumed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Gate Results (pre-design)

| Article | Gate | Result |
|---------|------|--------|
| I Local-first by default | No new network paths; the probe runs offline | ✅ PASS |
| II Typed decisions, not text | No new question types or answer fields; the refusal is an HTTP error | ✅ PASS |
| III Agent-legible contract | Kit changes land with README and tests; instructions ≤ 2 KB; kit numbers come from measured output | ✅ PASS (R6) |
| IV Non-interfering lifecycle | Tests use random ports. The probe opens no ports, stops nothing it didn't start, and is never part of check, test, or CI | ✅ PASS (R8) |
| V Model loading | Loader contract unchanged; measured caps for registry entries and a conservative fallback for others; dependency pins unchanged | ✅ PASS |
| VI Apple Silicon and CUDA | Counting doesn't depend on the device; the probe records which device it ran on | ✅ PASS |
| VII Verification over assertion | Model-backed tests, plus real CLI, HTTP, and MCP checks in the quickstart | ✅ PASS |
| VIII Tooling | ruff, mypy strict, bandit, compile, tests | ✅ PASS |
| IX Vault | A planning discovery note now; the cap decision note when the probe lands | ✅ PASS |
| X Python conventions | One class per file; enums; Pydantic at boundaries; docstrings; `runtime.py` debt paid down | ✅ PASS (R3, R7) |
| XI TDD and coverage | Red-green per task; coverage floor 81% | ✅ PASS |
| XII Async-first | No new routes; `/health` stays async; the engine route keeps its exception tag | ✅ PASS |
| XIII Layers | Counting lives in the engine, 413 mapping in HTTP; MCP untouched; doctor reads `/health` and a torch-free resolver; `Limits` is Pydantic across layers | ✅ PASS |
| XIV Pit of success | 413 instead of a crash; doctor never crashes, falling back to configured or unknown labels | ✅ PASS |
| XV Simplicity | Reuses `encode_record`, `evals.metrics`, `write_atomic`, and `copy_atomic`; no new endpoint, metric, or dependency | ✅ PASS (see Complexity Tracking) |

## Project Structure

### Documentation (this feature)

```text
specs/003-context-window-audit/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0: decisions R1–R16
├── data-model.md        # Phase 1: entities, fields, rules, state transitions
├── quickstart.md        # Phase 1: validation run book
├── contracts/
│   ├── config.md        # max_length / max_request_length resolution
│   ├── http-api.md      # /health fields, 413 refusal, 500 invariant
│   ├── mcp-tool.md      # refusal pass-through to the agent
│   ├── cli.md           # doctor limits line, ember eval context, make targets
│   ├── agent-kit.md     # guidance surfaces, byte budget, numbers test
│   └── eval-context.md  # probe artifacts, rescore and reproduce guarantees
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit.tasks)
```

### Source Code (repository root)

```text
ember/
  serving/
    limits.py            # NEW  Limits (Pydantic); resolution; model_max_length / declared_max_length; FALLBACK_* (torch-free)
    limit_source.py      # NEW  LimitSource StrEnum
    governing_limit.py   # NEW  GoverningLimit StrEnum (cap or maximum)
    request_size.py      # NEW  RequestSize; measure() via encode_record; refusal_message()
    devices.py           # NEW  pick_device / pick_dtype moved from runtime.py (§10.18 paydown)
    runtime.py           # MOD  Engine takes Limits; full-size check; invariant; describe() fields; < 400 lines
    media.py             # MOD  takes ALLOWED_MEDIA_KWARGS and its check
    server.py            # MOD  lifespan resolves Limits (registered or not) and logs them
  models.py              # MOD  ModelSpec.max_request_length; registry_key()
  cfg/config.py          # MOD  DEFAULTS["max_request_length"] = None
  commands/doctor.py     # MOD  limits line
  commands/endpoint.py   # MOD  endpoint_status() also returns the health engine
  commands/eval.py       # MOD  cmd_eval_context
  commands/parser.py     # MOD  eval context subparser
  cli.py                 # MOD  wire cmd_eval_context
  agent_kit/instructions.md, agent_kit/ember-advise/SKILL.md, agent_kit/AGENTS.snippet.md   # MOD
packages/claude-plugin/skills/ember-advise/SKILL.md                                       # MOD (mirror)
scripts/smoke_mps.py     # MOD  follow moved imports
evals/
  eval/provenance.py     # NEW  git_hash, git_dirty, host_info, model_spec_info (from run_evals.py)
  eval/run_evals.py      # MOD  import the provenance helpers (behavior unchanged)
  context/               # NEW  long-context probe
    __init__.py
    run_context.py       #      entry: pilot gate → per-model workers → summarize; rescore / reproduce / snapshot (orchestration only)
    items.py             #      item selection, exclusions, exploratory subset, manifest assembly
    reproduce.py         #      reproduction comparator (rows; verdicts for full runs only)
    worker.py            #      one model per process: in-process Engine, cells, appended rows, resume
    padding.py           #      filler slicing and depth placement to hit a target total
    filler.py            #      load and verify the vendored corpus; deterministic offsets
    filler.txt           #      public-domain text (SHA-256 pinned)
    memory_sampler.py    #      MemorySampler: polls torch.mps.driver_allocated_memory
    scoring.py           #      per-item accuracy and Brier, paired deltas, bootstrap_ci
    rule.py              #      the FR-010 rule (pure)
    summarize.py         #      rows + manifest → ProbeSummary (deterministic)
    records/             #      Pydantic models and enums, one class per file
      __init__.py, depth.py, row_status.py, failure_reason.py, probe_model.py, probe_manifest.py,
      probe_row.py, cell_result.py, length_verdict.py, model_verdict.py, probe_summary.py
    runs/                #      tracked snapshots of runs that decisions cite
shared/testing.mk        # MOD  eval-context, eval-context-smoke
tests/
  test_limits.py         # NEW  resolution table, clamping, invalid env, registry fallback, torch-free import
  test_request_size.py   # NEW  split arithmetic (fake joint module), refusal_message variants, no "/" in messages
  test_context_probe.py  # NEW  padding, depths, filler hash, rule, bootstrap, summarize determinism, resume, sizing math
  test_limits_model.py   # NEW  @model: exact counts vs encode_record, FR-003, boundary, config sweep, invariant, ~1M-token state
  test_runtime_unit.py, test_media.py, test_http_api.py, test_mcp_tool.py, test_cli.py, test_agent_kit.py   # MOD
README.md, COMPATIBILITY.md, AGENTS.md, THIRD_PARTY_NOTICES.md, docs/stride-review.md, docs/stride-tracker.csv   # MOD
.specify/memory/constitution.md   # MOD  PATCH: remove runtime.py from §10.18
vault/                            # NEW  planning discovery note; cap decision note (US3)
```

**Structure Decision**:
- **Runtime changes** stay in `ember/serving/`, which already holds the engine and HTTP
  layers. The resolver must be importable by the CLI without torch, and `cfg/` can't
  import `models.py`, so it can't live in `cfg/`.
- **The probe** is a new `evals/context/` package next to `evals/eval/` and
  `evals/agent/`. Its on-disk records are grouped under `records/`.

## Phase 0: Outline & Research

[research.md](./research.md) resolves every unknown:

| Decision | Topic |
|----------|-------|
| R1 | Counting method (telescoping `encode_record`) |
| R2 | Check placement, validation order, invariant |
| R3 | Resolution and the `None` sentinel |
| R4 | Reporting surfaces |
| R5 | MCP redaction constraint |
| R6 | Kit byte budget |
| R7 | `runtime.py` debt |
| R8 | In-process probe with per-model workers |
| R9 | Items, evidence, filler |
| R10 | Metrics, paired intervals, sizing gate |
| R11 | MPS peak-memory sampling |
| R12 | The rule |
| R13 | Artifacts and reproduction |
| R14 | CLI and make wiring |
| R15 | Very large states |
| R16 | Interim behavior |

No NEEDS CLARIFICATION remains.

## Phase 1: Design & Contracts

- **[data-model.md](./data-model.md)**: `LimitSource`, `Limits`, the `ModelSpec` addition,
  `RequestSize`, the refusal, the health fields, the limit report, and the probe records
  with their lifecycle.
- **[contracts/](./contracts/)**: configuration, HTTP, MCP, CLI, agent kit, and probe
  artifacts.
- **[quickstart.md](./quickstart.md)**: validation, from the unit gates to choosing the
  caps.

### Delivery order

1. **US1 and US2 foundation**:
   - New modules: `limits.py`, `limit_source.py`, `governing_limit.py`, `request_size.py`,
     `devices.py`.
   - Changes to the engine, server, `/health`, and doctor.
   - Defaults stay at 32,768 (`fallback`). The only behavior change is that the whole
     request is now counted.
   - In the same change, update the code references in STRIDE D-002 and update
     `AGENTS.md` (constitution workflow gate 4).
2. **US4, first pass**: README, COMPATIBILITY, and the kit describe exact counting,
   refusal, and the interim 32,768 default.
3. **US3**:
   - Build the probe package and CLI.
   - Run the smoke run, then the pilot, then the full canonical run, and snapshot it.
   - Set the `REGISTRY` caps, write the decision note superseding D-002, and update the
     STRIDE entries.
4. **US4, final pass**: Update the numbers everywhere. The kit-numbers test passes with
   the measured values.

### Modules to change

| Module | Change |
|--------|--------|
| `ember/serving/limits.py` (new) | `Limits` (frozen Pydantic: values, sources, `enforced`, `governing`); `resolve()` (pure); `from_config()`; `declared_max_length()`; `model_max_length()`; `FALLBACK_MAX_LENGTH`, `FALLBACK_REQUEST_CAP` |
| `ember/serving/limit_source.py` (new) | `LimitSource` StrEnum |
| `ember/serving/governing_limit.py` (new) | `GoverningLimit` StrEnum (`cap`, `maximum`), the type of `Limits.governing` (Article X §10.7) |
| `ember/serving/request_size.py` (new) | `RequestSize`; `measure(js, processor, request)`; `refusal_message(size, limits, declared)` |
| `ember/serving/devices.py` (new) | `pick_device` and `pick_dtype`, moved unchanged |
| `ember/serving/runtime.py` | `Engine(…, limits: Limits \| None = None)` replaces `max_length` and `max_request_length`. Size check before the lock; invariant after `systemone`; `describe()` gains three fields; imports from `devices`, `media`, and `limits` |
| `ember/serving/media.py` | `ALLOWED_MEDIA_KWARGS` and `check_media_kwargs()` |
| `ember/serving/server.py` | `lifespan` builds `Limits` with `limits.from_config(model_dir, models.registry_key(name))` (`None` for hosted) and logs them. 413 mapping unchanged |
| `ember/models.py` | `ModelSpec.max_request_length: int \| None = None`; `registry_key(name)`, which returns `None` when `EMBER_MODEL_DIR` is set |
| `ember/cfg/config.py` | `max_request_length` defaults to `None`; comment updated |
| `ember/commands/endpoint.py` | `endpoint_status()` adds `engine` from the health body |
| `ember/commands/doctor.py` | `limits` line (live, configured, or unknown) |
| `ember/commands/eval.py`, `parser.py`, `ember/cli.py` | `ember eval context` |
| `scripts/smoke_mps.py` | Follow the moved imports |
| `evals/eval/provenance.py` (new), `run_evals.py` | Extract the shared provenance helpers; add `git_dirty` |
| `evals/context/**` (new) | The probe (R8–R13). `run_context.py` only orchestrates; item selection lives in `items.py` and the reproduction comparator in `reproduce.py`. `FailureReason` is an enum in `records/failure_reason.py` |
| `shared/testing.mk` | `eval-context`, `eval-context-smoke` |
| Kit (3 files) and plugin mirror | Limits and refusal guidance ([agent-kit.md](./contracts/agent-kit.md)) |
| `README.md`, `COMPATIBILITY.md`, `AGENTS.md` | Config rows, the `413` metrics status, counting semantics, `make eval-context`, watch-outs, recent changes |
| `docs/stride-review.md`, `docs/stride-tracker.csv` | D-002: describe the new mechanism, then mark it superseded by the measured caps |
| `THIRD_PARTY_NOTICES.md` | Filler source and licence |
| `.specify/memory/constitution.md` | PATCH: remove `runtime.py` from §10.18, with a Sync Impact Report (3.1.1 → 3.1.2) |

### Tests to add or change

| Test file | Coverage |
|-----------|----------|
| `tests/test_limits.py` (new) | Every row of the resolution table; clamping; invalid and negative env values; registry measured value, fallback, and unregistered minimum; `enforced` and `governing`; importing `ember.serving.limits` doesn't import torch; the `model_max_length` tests, moved here |
| `tests/test_request_size.py` (new) | Split arithmetic with a fake `encode_record`; the text-only shortcut; refusal message variants (cap, operator-set maximum, declared maximum, fixed overhead alone); no `/` or `\`; at most 600 characters |
| `tests/test_runtime_unit.py` | D-002 tests updated for the new default and full counting (the fakes gain `encode_record`); an invariant mismatch raises; the `describe()` fields; device tests follow `devices.py` |
| `tests/test_media.py` | `check_media_kwargs` allowlist, moved from `runtime.py`, with the same messages |
| `tests/test_http_api.py` | `/health` engine fields; 413 body shape and message; 500 on a mismatch |
| `tests/test_mcp_tool.py` | The 413 `ToolError` text is exactly equal (stub endpoint); a model-backed MCP stdio test refuses an oversized state end to end (Article XI §11.4) |
| `tests/test_cli.py` | Doctor limits line: live local, live remote, configured, unreachable remote, older server; `ember eval context` dispatch |
| `tests/test_agent_kit.py` | Instructions are at most 2,048 bytes and include the refusal sentence; the kit's numbers equal the resolver defaults; README and COMPATIBILITY state every registered cap and the refusal (SC-005); the skill explains measured vs. fallback, and its quoted refusal fragments match `refusal_message` |
| `tests/test_context_probe.py` (new) | Padding lands in [L − 32, L] (fake counter); depth placement; filler SHA check; record constraints (exploratory subset membership, verdict field types); the rule (worst depth, memory gate, stop at the first failure, no passing length, `FailureReason` on failing verdicts); bootstrap determinism; byte-identical rescore; per-length median latency; resume after a torn line; item selection and the exploratory subset; sizing-gate math; subset reproduction compares rows only; no-MPS exit |
| `tests/test_limits_model.py` (new, `model`) | Exact totals vs `encode_record` on dict, string, and image fixtures; the FR-003 known-length check; boundary (the limit is served, limit + 1 is refused); refusal matrix over {dict, string, image} × three configurations (SC-002); the invariant on served requests; a ~1M-token state refused within 60 s with RSS growth under 2 GiB (FR-014); the same state refused with the cap disabled and the declared maximum governing; every measured registry cap within [2048, declared maximum] |

## Constitution Check — Post-Design Re-Evaluation

| Article | Result | Notes |
|---------|--------|-------|
| I | ✅ PASS | The filler is vendored; nothing downloads during a probe |
| II | ✅ PASS | Answer schema untouched; 413 body shape unchanged |
| III | ✅ PASS | Kit contract with a numbers test; the mirror is enforced; the instructions budget is checked |
| IV | ✅ PASS | Probe workers are child processes that the probe starts and waits for. No ports. A running server gets a warning and is otherwise left alone |
| V | ✅ PASS | Measured caps live in `REGISTRY` as a default, not a gate. The invariant holds for any loaded `joint_schema_model.py` |
| VI | ✅ PASS | Counting doesn't depend on the device; the plan states the probe runs on MPS only |
| VII | ✅ PASS | The quickstart exercises HTTP, MCP, and the CLI for real |
| VIII | ✅ PASS | — |
| IX | ✅ PASS | The discovery note is written with this plan; the decision note waits for the canonical run |
| X | ✅ PASS | New classes, one per file; fixed sets are enums (`LimitSource`, `GoverningLimit`, `Depth`, `RowStatus`, `FailureReason`); Pydantic for `Limits` and the probe records; `runtime.py` under 400 lines and removed from §10.18 |
| XI | ✅ PASS | Every module has a test file; model-backed tests run locally |
| XII | ✅ PASS | — |
| XIII | ✅ PASS | `limits.py` (torch-free) is shared by HTTP and the CLI. The engine imports no network code, and no torch tensors cross layers |
| XIV | ✅ PASS | Over the limit → 413. A size mismatch → 500 with a log entry, never a wrong answer. Doctor degrades to configured or unknown |
| XV | ✅ PASS | Two deliberate deviations from existing patterns are recorded below |

## Complexity Tracking

| Deviation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| The probe uses an in-process `Engine` in per-model worker processes, unlike `run_evals.py`, which calls the live server over HTTP | Peak MPS memory can only be observed in the process that owns the allocations. The probe also needs the cap disabled, long inferences outlast the 300 s client timeout, and each process can hold only one model (`runtime.py` L20–24) | Using the live server with `ps` sampling misses private Metal memory, and it would mean reconfiguring and restarting the user's server |
| `ember/serving/` grows to 10 peer modules (§10.3 asks to evaluate decomposition at 6) | One class per file plus the `runtime.py` debt paydown add `limits.py`, `limit_source.py`, `governing_limit.py`, `request_size.py`, and `devices.py` | A `serving/limits/` sub-package would add a level for five small, cohesive modules. Evaluated; not warranted |
| `evals/context/` has 10 peer modules (same §10.3 evaluation) | Splitting `items.py` and `reproduce.py` out of `run_context.py` keeps every module under 400 lines; the records already sit in `records/` | Merging modules would push `run_context.py` past 400 lines (§10.3); deeper nesting adds a level without making anything clearer |
