<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/hero-dark.svg">
  <img src="assets/brand/hero-light.svg" alt="ember — Ember hugs its glowing tummy. Give your agent a gut feeling." width="1200">
</picture>

[Brand assets and palette](assets/brand/README.md) · [Provenance and licensing](PROVENANCE.md) · [Project site](https://shapeandshare.github.io/ember/)

**A local gut feeling for coding agents.** ember runs
[Cloudflare's Clef-Flash](https://huggingface.co/Cloudflare/clef-flash) model on your Apple
Silicon Mac and gives agents one MCP tool, `advise`: describe a situation, ask typed
questions, and get back a calibrated feeling about every option. It's a little buddy for
judgment calls — it advises; the agent decides.

## How it works

Clef is a decision model, not a chat model: it takes a `state` plus a schema of typed
questions and returns one probability per option, with no text generation. So ember
plugs into agents as a **tool**, while their reasoning stays on their normal LLM:

```
coding agent ──(MCP tool: ember_advise)──► ember-mcp (stdio, starts instantly)
                                             │  instructions + ember://guide
                                             ▼  starts the server on first call
                                    ember model server (HTTP, stays warm)
                                             ▼
                                    Clef-Flash on MPS (fp16)
```

- The **model server** (`ember/server.py`) loads the model once and stays warm across
  agent sessions.
- The **MCP server** (`ember/mcp_server.py`) never loads the model; it starts the model
  server on the first tool call, so the MCP handshake stays instant.

### Names

| Thing | Name |
| --- | --- |
| Product, Python import, repository | `ember` |
| Distribution (`uv tool install`, PyPI) | `gut`, because `ember` is taken on PyPI |
| CLI | `ember` (short alias: `gut`) |
| MCP server / command | `ember` / `ember-mcp` |
| Tool | `advise` — opencode: `ember_advise`; Claude Code: `mcp__ember__advise` |
| Playbook skill / MCP resource | `ember-advise` / `ember://guide` |
| Environment variables | `EMBER_*` |

"Clef" always refers to Cloudflare's upstream model, never to this product.

## Verified

On a MacBook Pro **M4 Max / 128 GB**, torch 2.14.1, transformers 5.18.0, mcp 2.3:

| Step | Result |
| --- | --- |
| Model load | ~5 s |
| Warm request | **~0.9–1.3 s** for ~220–360 input tokens |
| opencode end to end | ✅ the agent reads the instructions, lists the skill, and calls the tool unprompted |

## Install (Apple Silicon)

Requires macOS on Apple Silicon. The weights (~18 GB) download into Hugging Face's shared
cache (`~/.cache/huggingface`); config, state, and logs live in
`~/Library/Application Support/ember`.

```bash
uv tool install --python 3.12 "gut @ git+https://github.com/shapeandshare/ember"

ember model pull          # ~18 GB, resumable, disk-space checked
ember doctor              # platform, dependencies, model, and server
ember init --opencode     # register with opencode: config, plugin, and skill
```

Keep `--python 3.12`: uv otherwise picks your newest interpreter, which the pinned
torch/transformers stack is not tested on.

The repository is public, so the install above needs no credentials. To use SSH instead,
install from `git+ssh://git@github.com/shapeandshare/ember`.

Restart opencode and the agent gains `ember_advise`. The model server stays **lazy** —
it starts on the first tool call (or with `ember start`).

Everything is pinned for reproducibility: `flash` to the commit verified on MPS (`17f0b0a`),
`full` to its release commit (`2f3de3d`, not yet verified locally), and torch/torchvision to
the tested minor series. Set `EMBER_MODEL_DIR` to run another weights directory.

## Agent onboarding

Installing the tool is half the job; the other half is making agents **want** to consult it
at the right moments and read its answers sensibly. `ember/agent_kit/` ships that
guidance through every channel each agent actually reads:

| Channel | opencode | Claude Code | Codex CLI | How you get it |
| --- | --- | --- | --- | --- |
| MCP server instructions (when to consult, how to ask, how to read answers) | ✅ in the system prompt | ✅ (2 KB cap) | — | built in, nothing to do |
| `ember://guide` resource (full playbook) | ✅ via `read_mcp_resource` | ✅ | — | built in |
| `ember-advise` skill (playbook, loaded on demand) | ✅ | ✅ | ✅ | `ember agents install --agent <agent>` |
| AGENTS.md / CLAUDE.md policy block | ✅ | ✅ (CLAUDE.md) | ✅ | `ember agents show snippet >> AGENTS.md` |

```bash
ember init --opencode                  # opencode: config entry, plugin, and skill
ember agents install --agent claude    # .claude/skills/ember-advise/SKILL.md
ember agents install --agent codex     # .agents/skills/... (opencode reads this too)
ember agents show snippet >> AGENTS.md # then edit the project policy at the end
```

The skill is a playbook, not a reference card: the decision points worth consulting
ember about, copy-paste question sets for intent and readiness, failure triage, change
risk, routing, and effort, and starting confidence thresholds calibrated from observed model
output (re-measured whenever the pinned model revision changes). The snippet ends with a
**project policy** — edit it to wire ember into your own workflow, e.g. "check change
risk before every push".

Agent-specific notes:

- opencode reads skills from `.opencode/skills`, `.claude/skills`, and `.agents/skills`, so
  install one copy per project to avoid duplicate listings.
- Claude Code: register the server with `claude mcp add ember -- ember-mcp`; the
  tool appears as `mcp__ember__advise`.
- Codex CLI support for MCP server instructions and resources is unconfirmed, so rely on the
  skill and the AGENTS.md snippet there.

## CLI

`gut` is a short alias for every command below.

```bash
# lifecycle
ember doctor                      # platform, dependencies, model, and server
ember serve                       # run the model server in the foreground
ember start | stop | restart | status | logs
ember config path | show
ember uninstall [--purge-models]  # also removes global opencode/skill installs

# models
ember model pull [flash|full]     # flash = 9B (default), full = 27B
ember model list | path [name] | rm [name]

# opencode and agents
ember init [--opencode] [--global]
ember agents install [--agent opencode|claude|codex] [--global]
ember agents show instructions|skill|snippet
ember mcp                         # the MCP stdio server agents launch
```

## Usage

Ask the agent in natural language — "Is this bug report urgent, and which team should own
it?" — and it calls `ember_advise` with a state and typed questions:

```json
{
  "model": "clef-flash",
  "answers": {
    "urgent": { "type": "noul", "noul": 0.967 },
    "team": {
      "type": "choice",
      "choice": "db",
      "confidence": 0.9782,
      "probabilities": { "db": 0.9782, "frontend": 0.0218 }
    }
  },
  "usage": { "input_tokens": 220, "output_tokens": 0 },
  "latency_ms": 930.9
}
```

Question types: `noul` (yes/no → P(true)), `choice` (named options), `score` (ordered options →
expected score plus legend). The `model` field echoes the upstream model label.

When the evidence is visual, attach images or video frames inline: `images` is a list of
`data:image/png;base64,...` URIs (or `{"content_type": "image/png", "base64": "..."}`
objects), and `videos` is a list of videos, each a list of frame refs. Remote URLs and local
paths are rejected — the model server never reads host files or fetches URLs for an agent.

## Configuration

Settings resolve as **CLI flag > environment variable > config file > default**. The config file
is JSON at `ember config path` (keys `model`, `host`, `port`, `device`, `max_length`; a
`max_length` of `0` means the model's own maximum).

| Variable | Default | Purpose |
| --- | --- | --- |
| `EMBER_HOST` / `EMBER_PORT` | `127.0.0.1` / `8765` | Model server address |
| `EMBER_DEVICE` | `auto` | `auto`, `mps`, or `cpu` |
| `EMBER_MODEL` | `flash` | `flash` (9B) or `full` (27B) |
| `EMBER_MODEL_DIR` | — | Run weights from this directory instead of the pinned cache |
| `EMBER_MAX_LENGTH` | `0` (the model's maximum: 262144) | Token cap per request; `0` derives it from the model |
| `EMBER_SERVER_URL` | `http://127.0.0.1:8765` | Where the MCP server sends requests |
| `EMBER_AUTOSTART` | `1` | Let the MCP server start the model server on demand |
| `EMBER_START_TIMEOUT` | `300` | Seconds to wait for the model server to start |
| `EMBER_STATE_DIR` | Application Support | Where the pid file and logs live |

## Metrics

While the model server is running it exposes Prometheus metrics at
`http://127.0.0.1:8765/metrics` (the `EMBER_HOST`/`EMBER_PORT` address):

| Metric | Type | Meaning |
| --- | --- | --- |
| `ember_advise_requests_total{status}` | counter | advise requests by HTTP status (`200`, `422`, `503`, `500`) |
| `ember_advise_latency_seconds` | histogram | advise request latency by status |
| `ember_advise_input_tokens_total` | counter | input tokens processed |
| `ember_advise_output_tokens_total` | counter | output tokens produced |
| `ember_model_info{model,device,dtype}` | gauge | `1` while a model is loaded |

The endpoint binds to the same address as the rest of the API (loopback by default), so
it is reachable only there unless you change `EMBER_HOST`. Ember's metrics live in a
dedicated Prometheus registry, so the standard `python_*`/`process_*` collectors are not
included — `/metrics` shows only the table above.

## Development

```
ember/
  cli.py              # the `ember` command (alias `gut`)
  runtime.py          # MPS-safe loader (CPU load → .to("mps")) + Engine
  server.py           # FastAPI: POST /v1/systemone, GET /health (reports pid)
  mcp_server.py       # MCP stdio server: advise tool, instructions, ember://guide
  process.py          # model-server lifecycle (pid file + HTTP health)
  models.py           # pinned model registry + pull/list/rm
  paths.py config.py  # platform dirs, config precedence
  opencode_config.py opencode_plugin.py   # opencode integration
  agent_kit/          # what agents read: instructions, ember-advise skill, AGENTS snippet
packages/opencode-plugin/   # npm-ready opencode plugin source
scripts/              # MPS smoke test, MCP end-to-end check, provenance and vault audits
tests/                # pytest suite (unit + model-backed, host-isolated)
vault/                # project memory (Obsidian): decisions, discoveries, session logs
.specify/             # spec-kit; memory/constitution.md governs this repo
AGENTS.md CLAUDE.md   # guidelines for agents working on this repo
Makefile              # contributor lifecycle (wraps the CLI)
```

```bash
make bootstrap    # deps + pinned weights + opencode.json + doctor (idempotent)
make start        # model server in the background; stop | restart | status | logs
make opencode     # this checkout's opencode plugin and skill
```

`opencode.json`, `.opencode/plugins/ember.js`, and `.opencode/skills/ember-advise/`
embed this clone's absolute paths or copy packaged files, so they are gitignored — regenerate
them with `make init` / `make opencode` after cloning. `.opencode/opencode.json` is shared and
committed: it registers the `vault` MCP server that agents use to read and write `vault/`
(launch opencode from the repository root).

### Make targets

| Target | What it does |
| --- | --- |
| `make help` | List all targets (default) |
| `make bootstrap` | From a fresh clone: `setup` + `init` + `doctor` |
| `make setup` / `sync` / `download` | Deps + weights / deps only / pinned weights to `.models/` |
| `make init` / `make opencode` | `ember init` / `ember init --opencode` for this checkout |
| `make serve` / `start` / `stop` / `restart` / `status` / `logs` | Model-server lifecycle via the CLI |
| `make mcp` / `make mcp-list` | Run the MCP server / `opencode mcp list` |
| `make test` / `test-fast` / `test-strict` | Full suite / unit tests only / full suite that fails without weights |
| `make test-evals` | Calibration eval suite: positive + negative recipe cases (loads model) |
| `make eval-run` | Run the benchmark dataset against the live server; writes `results/` |
| `make eval-snapshot` | Copy the latest run into `benchmark/` for the site to render |
| `make eval-report` | Render the most recent run as a Markdown table |
| `make mcp-check` / `make smoke` | MCP end-to-end check / direct MPS inference |
| `make compile` / `make check` | Byte-compile / compile + unit tests |
| `make ci` | `bootstrap` + `check` + `test-strict` |
| `make doctor` | `ember doctor` |
| `make vault-audit` | Check `vault/` notes: frontmatter, tags, wikilinks, code-refs, orphans |
| `make site` / `make site-serve` | Build the Pages site into `site/_site` / preview it at `:4000` (needs Docker) |
| `make clean` / `make clean-model` | Caches and build output / weights (`EMBER_FORCE=1` skips the prompt) |

Make re-syncs the environment automatically when `pyproject.toml` or `uv.lock` changes.

## Tests

```bash
make test         # full suite (~30 s, loads the model once)
make test-fast    # unit tests only, no model load (~12 s)
make check        # compile + test-fast
make test-strict  # full suite; fails (not skips) if weights are missing
make ci           # bootstrap + check + test-strict
```

`tests/` covers the supported call paths:

- `GET /health` and `POST /v1/systemone` across `noul` / `choice` / `score`, probability
  normalization, and request-validation `422`s
- MCP tool discovery, `advise` over stdio, actionable errors (server down, model missing,
  malformed questions), and autostart on a configured port with pid cleanup
- the agent kit: instructions size, skill frontmatter, the `ember://guide` resource
- the CLI: `agents`, `init --opencode`, `status`/`stop` on unused ports, `doctor`, `uninstall`
- process safety: `stop` never signals a pid that is not an ember server it started

**Safe on a host running other opencode instances.** The suite binds random free ports (never
`8765`), keeps state in temporary directories, stops only the processes it started, and never
invokes the opencode CLI or touches global opencode config.

**CI** (`.github/workflows/ci.yml`) runs `uv sync --locked`, `make check`, `uv build`, and an
install smoke of the built wheel on a hosted Apple Silicon runner, and audits the workflows
with [zizmor](https://docs.zizmor.sh). Model-backed tests are
**not** run in CI: the ~19 GB fp16 model does not fit the available runners (hosted or the
org's 8 GiB self-hosted VMs), so run `make test` locally for model-affecting changes.

### Benchmark

`evals/clef-flash.jsonl` is a 264-item benchmark covering the five agent-kit recipes (intent
and readiness, failure triage, change risk, routing, effort and approach) plus four vision
recipes (`vision_noul`, `vision_choice`, `vision_score`, `vision_video`): 456 scored questions
(184 `choice`, 152 `noul`, 88 `score`, 32 across the four vision recipes), split into
`dev` (130 items) and `test` (134). Vision items carry an `images` or `videos` field
(base64 `data:` URIs) alongside `state` and `questions`. Each line is
self-contained (`state`, the recipe's fixed question set, a gold label for every question, and
a `rationale`), so other implementations can score it without this harness.

```bash
make eval-run       # or: ember eval run [--split dev|test] [--category <recipe>]
make eval-report    # Markdown report of the most recent run
make eval-export    # or: ember eval export; the reviewer bundle described below
ember eval report --compare results/<a>_results.json results/<b>_results.json
```

`ember eval export` writes `results/<run_id>_report/` for external reviewers:
`report.html` (one self-contained file with inline charts, light and dark themes, a print
layout, and item filters; it loads nothing from the network), `report.md` with its
`figures/*.svg`, and `data/` with the run's results, trace, and the exact dataset scored.
The report covers context, the system under test, benchmark design, metric definitions with
references, results, calibration, the agent kit's decision rules replayed on every item, a
review card for every miss, limitations, and reproduction pins.

The report gives accuracy with a 95% bootstrap interval, macro-F1, top-label ECE, and Brier
score (`choice`, `noul`); ranked probability score and MAE (`score`); and coverage and accuracy
at the agent kit's act-on-it thresholds. Each run records the git hash, the engine, and the
dataset's SHA-256, and `--compare` warns when two runs scored different item sets.

Gold labels are judged from `state` alone against the recipe's option descriptions, and they
are fixed before any run: `needs_review` is true exactly when `risk` is Medium or High, and
`retry` only for `flaky` failures. A person reviews disagreements; labels are never changed to
match the model. `make check` validates the dataset (`tests/test_eval_benchmark.py`).
`ember eval` reads `evals/` and `scripts/` from the checkout, so it works only in a clone.

### Agent in the loop

The benchmark above scores the model. `ember eval agent` scores ember the way it is used:
through a coding agent. It gives opencode 54 scripted requests (vague and precise asks,
failing tests, risky and trivial commits, routing and effort questions, and controls), each
in a throwaway git repo, and judges the agent only by what it did (files, commits, tests,
its reply). Each scenario runs under four conditions: `none` (no ember), `mcp` (the MCP
server and its instructions), `skill` (plus the `ember-advise` skill), and `full` (plus the
AGENTS.md policy).

```bash
ember start                       # the agent sessions call the warm server
make eval-agent-smoke             # 6 scenarios x 4 conditions x 2 models, 1 trial
make eval-agent                   # or: ember eval agent [--models ...] [--trials 3] [--parallel 8]
ember eval export --agent latest  # put the agent results first in the reviewer report
```

Every session runs `opencode run --pure` with a private HOME and XDG directories and no TCP
port, so your opencode config, plugins, sessions, and running instances are untouched. The
provider key is read from the environment or opencode's auth file and passed only to the child
process. The run reports, per model and condition: gold-action accuracy, its paired change
against `none`, how often the agent consulted ember at decision points (and on controls),
whether it consulted before acting, asked the kit's recipe questions, passed the evidence, and
followed ember's answer, plus cost and time per session. It spends real provider credit and is
never part of `make check`, `make test`, or CI.

## Caveats

- **Gated DeltaNet fallback.** Qwen3.5's backbone is a hybrid linear-attention model. The
  optimized CUDA kernels (`causal_conv1d`, `flash-linear-attention`) don't exist for Apple
  Silicon, so it uses the pure-PyTorch reference path: **correct but slower**. You'll see two
  "falling back" log lines — expected.
- **fp16 on MPS.** `bfloat16` works but is emulated and less battle-tested on MPS, so the
  loader uses `float16`; CPU mode uses `float32`.
- **Vision works on MPS.** Images and video frames run through the same fp16 path as text.
  Inline them as base64 `data:` URIs in `images`/`videos`; remote URLs and local paths are
  rejected on purpose, so an agent cannot make the server read host files or fetch URLs.
  Text-only inputs skip the vision tower entirely.
- **Numerics.** MPS can differ slightly from CUDA/CPU. If calibrated probabilities matter,
  cross-check with `EMBER_DEVICE=cpu ember restart`.
- **`device_map={"": "mps"}` segfaults** with the pinned stack. The loader loads on CPU and then
  moves the model to MPS — don't "simplify" that away.

## Troubleshooting

- Start with `ember doctor`, then `ember logs`
  (`~/Library/Application Support/ember/logs/server.log`).
- The agent can't see the tool: `opencode mcp list` should show `✓ ember connected`.
- "model … is not pulled": run `ember model pull`, or point `EMBER_MODEL_DIR` at the
  weights.
- `Qwen3VLVideoProcessor requires Torchvision` → torchvision is a pinned dependency; run
  `uv sync` (or reinstall the tool).
- Any single unimplemented MPS op falls back to CPU (`PYTORCH_ENABLE_MPS_FALLBACK=1`, set by the
  runtime).

## License

MIT (see `LICENSE`). Cloudflare's Clef weights and `joint_schema_model.py` are Apache-2.0; they
are downloaded from Hugging Face at runtime, not redistributed here.
