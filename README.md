# Clef-Flash Local → opencode MCP

Run [Cloudflare's Clef-Flash](https://huggingface.co/Cloudflare/clef-flash)
decision model **locally on an Apple Silicon Mac** and expose it to
[opencode](https://opencode.ai) as an MCP tool your coding agent can call for
fast, typed decisions.

## Why it's built this way

Clef is a **decision model**, not a chat model. It takes a `state` plus a schema
of typed `questions` and returns one probability per option — no text
generation, no tool calls. That means you **cannot** point opencode's model
provider at it. Instead:

```
opencode agent  ──(MCP tool: clef_decide)──►  MCP server (thin, fast)
   (reasoning stays on                        │
    your normal LLM)                          ▼
                                    warm HTTP server (holds the model)
                                              │
                                              ▼
                                    Clef-Flash on MPS (fp16)
```

- The **HTTP server** (`clef_local/server.py`) loads the model once and stays warm.
- The **MCP server** (`clef_local/mcp_server.py`) is a thin client; it starts the
  HTTP server on first use (if needed) so opencode's MCP startup stays instant and
  the model isn't reloaded per session.

## Verified

On a MacBook Pro **M4 Max / 128 GB**, torch 2.14.1, transformers 5.18.0, mcp 2.x:

| Step | Result |
| --- | --- |
| Model load | ~5 s |
| Warm inference | **~0.9–1.2 s** for ~220–360 input tokens |
| opencode tool call | ✅ `clef_decide` invoked, correct probabilities returned |

## Layout

```
clef_local/
  cli.py              # the `clef` command (lifecycle, models, doctor, init)
  runtime.py          # MPS-safe loader (CPU load -> MPS move) + ClefEngine
  server.py           # FastAPI: POST /v1/systemone, GET /health
  mcp_server.py       # MCP stdio server exposing the `decide` tool
  process.py          # warm-server lifecycle (pidfile + HTTP health, no bash/lsof)
  models.py           # model registry + pull/list/rm (flash default, full opt-in)
  paths.py            # platform dirs (config/state/log) + HF cache
  config.py           # config with flag > env > file > default precedence
  opencode_config.py  # write/merge the mcp.clef entry
  opencode_plugin.py  # install the local opencode plugin
packages/opencode-plugin/   # publishable opencode plugin source (npm-ready)
scripts/
  clef-server.sh      # dev server lifecycle (bash)
  smoke_mps.py        # direct MPS inference smoke test
  test_mcp_client.py  # MCP protocol end-to-end test
  doctor.sh           # readiness report (bash)
tests/                # pytest suite (see "Tests" below)
Makefile          # dev lifecycle commands (run `make help`)
opencode.json     # generated per machine by `clef init` / `make init` (gitignored)
pyproject.toml    # package + deps (installs `clef` and `clef-mcp`)
```

## Install (Apple Silicon)

Requires macOS on Apple Silicon. Weights (~18 GB) download on first pull into
HuggingFace's shared cache (`~/.cache/huggingface`); config/state live in
`~/Library/Application Support/clef-local`.

```bash
uv tool install "clef-local @ git+https://github.com/shapeandshare/gut-feeling"

clef model pull          # ~18 GB, resumable, disk-space checked
clef doctor              # env / model / server readiness
clef init --opencode     # install the opencode plugin (project) or --global
```

The repository is private, so installers need read access plus git credentials:
run `gh auth setup-git` once for HTTPS, or install from
`git+ssh://git@github.com/shapeandshare/gut-feeling` with SSH keys.

Restart opencode, and the agent gains a `clef_decide` tool. The model server
stays **lazy** — it starts on the first tool call (or `clef start`).

Everything is pinned for reproducibility: `flash` to the commit verified on MPS
(`17f0b0a`), `full` to its release commit (`2f3de3d`, not yet verified locally),
and torch/torchvision to the tested minor series. Set `CLEF_MODEL_DIR` to run any
other weights directory.

## CLI

```bash
# lifecycle
clef doctor                      # readiness report
clef serve                       # run the server in the foreground
clef start | stop | restart | status | logs
clef config path | show
clef uninstall [--purge-models]

# models
clef model pull [flash|full]     # flash = 9B (default), full = 27B
clef model list | path [name] | rm [name]

# opencode
clef init --opencode [--global]  # install the local opencode plugin
clef init                        # or just write the mcp.clef config entry
```

## Development setup

```bash
make bootstrap    # deps + pinned weights + opencode.json + readiness (idempotent)
# or individually: make sync, make download, make init
```

`opencode.json` and `.opencode/plugins/clef.js` embed this clone's absolute paths,
so they are gitignored — regenerate them with `make init` / `make opencode` after
cloning.

## Run

```bash
make doctor        # check env, weights, and server readiness
make start         # start the warm model server (background)
make status        # is it up?
make logs          # tail the server log
make stop          # stop it
make serve         # run it in the foreground instead
```

opencode reads the project `opencode.json` automatically — **restart opencode**
after first install so it picks up the MCP server. Verify:

```bash
make mcp-list      # → ✓ clef connected
```

### Make targets

| Target | What it does |
| --- | --- |
| `make help` | List all targets (default) |
| `make bootstrap` | From a fresh clone: `setup` + `init` + `doctor` |
| `make setup` | `sync` + `download` |
| `make sync` | Install/sync Python deps (uv) |
| `make download` | Fetch Clef-Flash weights (~18 GB) |
| `make init` | Regenerate `opencode.json` with this clone's absolute paths |
| `make serve` | Run model server in the foreground |
| `make start` / `stop` / `restart` | Background model server lifecycle |
| `make status` | Server health + engine info |
| `make logs` | Tail `logs/server.log` |
| `make mcp` | Run the MCP server in the foreground (debug) |
| `make mcp-list` | `opencode mcp list` |
| `make test` | Full test suite (loads the model once) |
| `make test-fast` | Unit tests only (no model load) |
| `make test-strict` | Full suite that **fails** if weights are missing (CI) |
| `make mcp-check` | MCP protocol end-to-end check |
| `make smoke` | Direct MPS inference smoke test |
| `make compile` | Byte-compile all modules |
| `make check` | `compile` + `test-fast` |
| `make ci` | `bootstrap` + `check` + `test-strict` (full gate) |
| `make doctor` | Environment / model / server readiness |
| `make clean` | Remove caches and stale pid files |
| `make clean-model` | Delete weights (`CLEF_FORCE=1 make clean-model` to skip the prompt) |

Override the server bind with env vars, e.g. `CLEF_PORT=9000 make start`.

### Fully programmatic (fresh clone → working agent)

```bash
make bootstrap      # deps + weights + opencode.json + readiness
make start          # warm the model (optional; opencode auto-starts it too)
make ci             # non-interactive gate: bootstrap + check + strict tests
```

Everything above is idempotent and non-interactive. The only manual step is
restarting a running opencode so it picks up `opencode.json`.

## Usage

Ask the agent in natural language; it will call `clef_decide` with a state and
typed questions. Examples:

- *"Is this bug report urgent? Which team should own it?"*
- *"Score how severe this incident is on No impact / Minor / Major / Critical."*
- *"Classify which module this change touches."*

The tool returns:

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

Question types: `noul` (yes/no → P(true)), `choice` (named options),
`score` (ordered options → expected score + legend).

## Tests

```bash
make test         # full suite (~35s, loads the model once)
make test-fast    # unit tests only, no model load (~11s)
make check        # compile + test-fast
make test-strict  # full suite; FAILS (not skips) if weights are missing — for CI
make ci           # bootstrap + check + test-strict
```

`tests/` covers the supported call paths:

- `GET /health` (device/dtype reporting)
- `POST /v1/systemone` across `noul` / `choice` / `score`, probability
  normalization, and request-validation `422`s
- MCP tool discovery and `decide` over stdio
- MCP error when the model server is down
- MCP autostart on a configured (non-default) port, with PID cleanup
- `opencode.json` merge/idempotency, pinned model revisions, and the management
  script (without invoking opencode)

**Safe on a host running other opencode instances.** The suite:

- binds a **random free port** and never the default `8765`,
- starts/stops **only the processes it owns** (tracked by PID; never kills by port),
- never invokes the opencode CLI or mutates global opencode config.

**CI** (`.github/workflows/ci.yml`): every push/PR runs `uv sync --locked`,
`make check`, `uv build`, and an install smoke of the built wheel as a uv tool on a
hosted Apple Silicon runner. Hosted runners lack the memory for the ~19 GB fp16
model, so the model-backed `make test-strict` job runs on manual dispatch against a
self-hosted Apple Silicon runner.

## Caveats

- **Gated DeltaNet fallback.** Qwen3.5's backbone is a hybrid linear-attention
  model. The optimized CUDA kernels (`causal_conv1d`, `flash-linear-attention`)
  don't exist for Apple Silicon, so it uses the pure-PyTorch reference path. This
  is **correct but slower**. You'll see two "falling back" log lines — expected.
- **fp16 on MPS.** `bfloat16` works but is emulated and less battle-tested on
  MPS; the loader uses `float16`. CPU mode uses `float32`.
- **Vision/video untested on MPS.** Text-only inputs skip the vision tower
  entirely (verified in Clef's own code), so text decisions are safe. Image/video
  on MPS is unproven.
- **Numerics.** MPS can differ slightly from CUDA/CPU. If calibrated
  probabilities matter, cross-check with `CLEF_DEVICE=cpu scripts/clef-server.sh restart`.
- **`device_map={"": "mps"}` segfaults** in this torch/transformers combo. The
  loader works around it by loading on CPU then moving to MPS. Don't "simplify"
  that away.

## Troubleshooting

- Server logs: `logs/server.log`
- MCP discovery failing in opencode: check `opencode mcp list`; the config uses
  the flat `mcp.<name>` shape this opencode build expects.
- `Qwen3VLVideoProcessor requires Torchvision` → `uv add torchvision` (already in deps).
- Any single unimplemented MPS op falls back to CPU (`PYTORCH_ENABLE_MPS_FALLBACK=1`,
  set by the runtime).

## License

Apache-2.0 (see `LICENSE`), matching the upstream Clef weights.
