# Deploying ember to Outerbounds

Deploy ember's model server itself (not a client) to Outerbounds, so an agent
elsewhere can reach it over `EMBER_SERVER_URL`. This follows the standard
[Outerbounds App](https://docs.outerbounds.com/) deployment contract.

## What this deploys

`ember serve` in the foreground, as a FastAPI/uvicorn app, loading a model from
an `s3://bucket/prefix` location (`EMBER_MODEL_S3_URI`) rather than a pinned
`REGISTRY` entry — there is no Hugging Face download at deploy time. See
`ember/serving/hosted.py` and README.md's "Hosted deployment: a model location
supplied at start time" for the mechanism, and constitution Article V ("Model
Loading") for why no integrity hash is checked against that location.

There are two deployment configs, one per model, because they need
materially different compute (see "Choosing the model and sizing GPU memory"
below) and Outerbounds requires each deployment to have a globally unique
`name`:

| File | Model | `name` | GPU floor |
| --- | --- | --- | --- |
| `deployment/flash.yaml` | `flash` (9B) | `ember-flash` | 24 GB (A10G, tight) |
| `deployment/full.yaml` | `full` (27B) | `ember-full` | 80 GB (H100/A100-80GB) |

Deploy each independently (`outerbounds app deploy --config-file deployment/<file>.yaml ...`);
they run as separate pods with separate URLs, and the benchmark leaderboard
(`/results/` on the site) shows each as its own row once you run the
benchmark against it (`EMBER_SERVER_URL` pointed at that deployment's URL).

## Prerequisites

1. **A GPU-backed compute pool sized for the model**, not just "has a GPU"
   (Outerbounds UI → Compute) for the CUDA path in `flash.yaml`/`full.yaml`
   (constitution Article VI, "Apple Silicon and CUDA" — CUDA is the
   hosted-deployment device; MPS is Apple-Silicon-only and unavailable on
   Outerbounds' Linux compute). A CPU-only pool works too — see "CPU-only
   deployment" below. Two distinct resources must both fit, and Outerbounds
   only validates one of them at deploy time:
   - **System RAM** (`resources.memory` in each file) is checked by the
     scheduler at deploy time — an undersized pool fails immediately with
     `AppCreationFailedException: ... memory requirement <X>Gi exceeds
     available <Y>Ki`. This happened against two different pools during this
     deployment's own setup, both capped
     around 14-15 GiB *schedulable* memory regardless of their advertised
     instance size — always confirm actual available memory, don't assume it
     matches the nominal instance type.
   - **GPU VRAM** (not a Kubernetes-schedulable resource; AWS instance choice
     is the only lever) is **not validated at deploy time at all** — an
     undersized GPU is silently accepted by the scheduler and only fails
     later, at model-load time inside the running pod, as a CUDA
     out-of-memory error in that pod's own logs. See "Choosing the model and
     sizing GPU memory" below before picking an instance type.
2. **An S3 bucket containing the model's files** (`config.json`,
   `joint_schema_model.py`, `joint_head.safetensors`,
   `joint_head_config.json`, `model.safetensors.index.json`, and the
   sharded `model-*.safetensors` weight files — the same shape
   `ember/models.py` downloads for `flash`/`full` from Hugging Face).
3. **No secret integration needed for the common case.** Both files ship
   with `secrets: []`:
   - Access control is `auth.type: API` (below) — Outerbounds gates the
     endpoint with each caller's own existing platform token, so ember's own
     optional `EMBER_SERVER_AUTH_TOKEN` bearer-auth layer is intentionally
     left unset for this deployment. (Setting `EMBER_HOST` to a non-loopback
     address with no `EMBER_SERVER_AUTH_TOKEN` is accepted by ember — see
     `docs/stride-tracker.csv` T-004 and `SECURITY.md`'s accepted-residual-
     risks section. Access control is the operator's responsibility in that
     configuration; here it's Outerbounds' gateway.)
   - S3 access relies on an IAM role attached to the compute pool; boto3's
     default credential chain picks it up automatically (see
     `vault/decisions/2026-10-08-optional-s3-credentials-iam-role.md`). Only
     add a secret integration with `EMBER_S3_ACCESS_KEY_ID`/
     `EMBER_S3_SECRET_ACCESS_KEY` if no role is attached.
4. **Outerbounds CLI configured** and authenticated against your workspace and
   perimeter. `outerbounds` is already in this repo's `dev` dependency group
   (`make setup`/`make sync` installs it into `.venv`), so `uv run outerbounds
   ...` works right away — no separate `pip install` needed:

   ```sh
   # Token comes from your workspace's Setup page (Getting Started → Workspace).
   uv run outerbounds configure <token from your workspace's Setup page>
   uv run outerbounds perimeter list                 # confirm "default" is available
   uv run outerbounds perimeter switch --id default  # target the default perimeter
   ```

## Deploy

```sh
# Regenerate requirements.txt from uv.lock — do this before every deploy so
# Fast Bakery resolves the exact dependency set CI/tests ran against. Both
# deployments share the same requirements.txt.
make deployment-requirements

# Fill in the chosen file's placeholders first (team/owner tags, and for
# full.yaml the model's S3 location and compute_pools — flash.yaml's are
# already filled in for the live flash deployment), then:
uv run outerbounds app deploy \
  --config-file deployment/flash.yaml \
  --package-src-path . \
  --readiness-condition async

# ...and/or, separately, for full:
uv run outerbounds app deploy \
  --config-file deployment/full.yaml \
  --package-src-path . \
  --readiness-condition async
```

`--readiness-condition async` matches `/health`'s own behavior: the endpoint
returns `200` with `{"status": "loading"}` immediately, before the model
finishes loading (constitution Article XIV, "Pit of Success") — Outerbounds
should mark the pod ready once the port responds, not once inference is
possible.

## Connecting a client

Point a remote agent at the deployed URL (the one `outerbounds app deploy`
prints, or your `generate_static_url: true` stable URL). Because `auth.type:
API` is set, Outerbounds requires each caller's own platform token as
`x-api-key` (not an ember-minted `EMBER_SERVER_AUTH_TOKEN` — see
[Writing your first Deployment](https://docs.outerbounds.com/outerbounds/first-inference-deployment/)
for how to obtain it, e.g. `METAFLOW_SERVICE_AUTH_KEY` from your local
Metaflow config at `~/.metaflowconfig/config.json`, or a minted machine-user
token for a non-interactive caller):

```sh
# Install the CLI first if it isn't already (uv tool install, not this repo's
# .venv — ember init --global must run from the installed tool so it records
# the right ember-mcp path):
uv tool install --python 3.12 ember-advise

# Register whichever harness(es) you use — --opencode, --kilocode, --codex
# can be combined; the same --server-url/--auth-header apply to all of them:
ember init --opencode --kilocode --global \
  --server-url https://<your-app>.outerbounds.app --auth-header x-api-key

export EMBER_AUTH_TOKEN=<your own Outerbounds/Metaflow API token>
# e.g.: export EMBER_AUTH_TOKEN="$(python3 -c \
#   "import json; print(json.load(open('$HOME/.metaflowconfig/config.json'))['METAFLOW_SERVICE_AUTH_KEY'])")"
```

`EMBER_AUTH_TOKEN` is **never** written to `opencode.json`/`kilo.json`/the
plugin file — export it in the shell that launches the agent (see README.md
"Remote inference"). `--auth-header` accepts any header name; `x-api-key` is
sent verbatim, `Authorization` (the default) is sent as `Bearer <token>`.
Restart the harness (opencode, Kilo Code) afterward to pick up the new MCP
registration.

### Verifying from the shell (`ember status` / `ember doctor`)

`ember init` only writes `server_url`/`auth_header` into the MCP entry's
environment block inside `opencode.json`/`kilo.json` — it does not change
ember's own config file, so running `ember status` or `ember doctor` directly
from your shell still reports the **local** default (`127.0.0.1:8765`)
unless you also point ember's own config at the remote endpoint:

```sh
# Either export the same variables in your shell:
export EMBER_SERVER_URL=https://<your-app>.outerbounds.app
export EMBER_AUTH_HEADER=x-api-key
export EMBER_AUTH_TOKEN=<your own Outerbounds/Metaflow API token>
ember status

# ...or persist server_url/auth_header (never the token) in ember's config
# file so you don't have to export them every session:
cat > "$(ember config path)" <<'JSON'
{
  "server_url": "https://<your-app>.outerbounds.app",
  "auth_header": "x-api-key"
}
JSON
export EMBER_AUTH_TOKEN=<your own Outerbounds/Metaflow API token>
ember status
```

A healthy remote deployment reports `"reachable": true, "ready": "ok"` with
an `engine` block describing the loaded model; `/health` is probed with the
same credential header as the real `advise` call, so a gateway-authenticated
deployment like this one (Outerbounds' `auth.type: API`) is never
misreported as unreachable.

## Choosing the model and sizing GPU memory

There is no runtime VRAM-limiting knob (no quantization, no multi-GPU sharding, no
`max_memory` ceiling) — ember always loads the full model in float16 on a single
device. **Size the GPU to the model, not the other way around**: pick
`resources.gpu`/the compute pool first, by checking your model against the
numbers in [`COMPATIBILITY.md`](../COMPATIBILITY.md#hardware-requirements)
(`flash` 9B needs roughly 18 GiB of weights plus activation/KV-cache headroom —
32 GB+ total is the practical floor on MPS and a reasonable floor on CUDA too;
`full` 27B needs roughly 55 GiB of weights and 96 GB+ total, since a request at its
65,536-token default peaked at 90.8 GiB on MPS). A GPU too small for the weights fails
with a CUDA out-of-memory error at load time, not a graceful degradation. One that holds
the weights but not a long request fails only when such a request runs; lower
`EMBER_MAX_REQUEST_LENGTH` to what the GPU can hold.

**System RAM and GPU VRAM are sized independently, and only one is a single
AWS "instance size" knob.** `load_clef()` (`ember/serving/runtime.py`) loads
the model on CPU first, then moves it to the GPU — so system RAM must
transiently hold the full float16 weights too, which is why each file's
`resources.memory` matches the GPU VRAM floor rather than being a much
smaller "just for the OS" number. Concretely:

| Model | Instance | GPU VRAM | System RAM | Fit |
| --- | --- | --- | --- | --- |
| `flash` (9B, ~18 GiB weights) | `g5.2xlarge` (1x A10G) | 24 GB (~22.3 GiB usable) | 32 GiB | VRAM: tight (~4 GiB headroom). RAM: matches the request almost exactly — little schedulable margin, risks the same "memory exceeds available" failure as an undersized pool. |
| `flash` | `g5.4xlarge` (1x A10G) | 24 GB (~22.3 GiB usable) | 64 GiB | VRAM: same tight ~4 GiB headroom as `g5.2xlarge` — bigger instance size does **not** add VRAM within the same GPU model. RAM: real margin below the 32Gi request. **This is `flash.yaml`'s target** (`ai-sage-inf-gpu`). |
| `flash` | `g6e.xlarge`+ (1x L40S) | 48 GB | varies | VRAM: comfortable headroom — AWS's own recommended upgrade path from G5 for memory-bound LLM serving. Not yet used or verified. |
| `full` (27B, ~55 GiB weights) | any G5/G6e size above | 24–48 GB | — | **Does not fit at all** — `full`'s weights alone (~55 GiB) exceed even L40S's 48 GB before activations/KV-cache are counted. |
| `full` | `p5.4xlarge` (1x H100) | 80 GB HBM3 | 256 GiB | VRAM: ~25 GiB headroom for activations/KV-cache after ~55 GiB of weights. RAM: comfortable margin above the 96Gi request. **This is `full.yaml`'s target** — not yet deployed or verified against real hardware. |

Every single-GPU size within one AWS GPU family (every `g5.*xlarge`, for
example) has the *identical* GPU and VRAM — only system RAM, vCPU, and disk
scale with instance size. A10G's ~22.3 GiB usable VRAM leaving only ~4 GiB
for `flash`'s activations and KV-cache is a **genuinely tight fit, not yet
verified against real NVIDIA hardware** (see COMPATIBILITY.md) — if the
pod's own logs show a CUDA out-of-memory error after the Kubernetes
scheduler already accepted the deployment, the fix is a bigger-VRAM GPU
model (e.g. L40S/G6e for `flash`, or P5/H100 for `full`), not a bigger
instance size of the same GPU. ember has no multi-GPU support
(`load_clef()` moves the whole model to one device), so a multi-GPU
instance such as `p4d.24xlarge` (8x A100 40 GB) does not help `full` either
— only a single GPU with enough VRAM on its own does.

Three independent settings control what actually loads and how much memory it
needs:

| Setting | Controls | Example |
| --- | --- | --- |
| `EMBER_MODEL_S3_URI` (or `EMBER_MODEL` for a `REGISTRY` entry) | **Which model** — this is what actually determines the VRAM requirement | `s3://my-bucket/clef-flash` (9B) vs. a `full`-sized (27B) location |
| `EMBER_DEVICE` | **Which accelerator** — `cuda`/`mps` load in float16 (smaller footprint); `cpu` loads in float32 (~2x the memory, see "CPU-only deployment" below) | `cuda` |
| `resources.gpu` / `compute_pools` in `flash.yaml`/`full.yaml` | **How much VRAM is actually available** — this is capacity planning, not a software setting; pick a pool whose GPU memory exceeds the chosen model's float16 footprint with headroom | a pool with 24–48 GB+ VRAM for `flash`, 80 GB+ for `full` |

`EMBER_MAX_LENGTH`/`EMBER_MAX_REQUEST_LENGTH` (see README.md's env var table) bound
context length, which indirectly affects KV-cache memory at long contexts, but
they are not a VRAM ceiling — they do not prevent an OOM if the base model
itself doesn't fit.

## CPU-only deployment

No GPU compute pool yet? Edit whichever of `flash.yaml`/`full.yaml` you're
deploying:

- `EMBER_DEVICE: "cpu"` instead of `"cuda"`.
- Remove `resources.gpu` and roughly double `resources.memory` (CPU loads in
  float32, about 2x the float16 footprint — see COMPATIBILITY.md).
- Point `compute_pools` at a CPU pool instead.

## Updating dependencies

`deployment/requirements.txt` is generated, not hand-maintained — never edit
it directly. Run `make deployment-requirements` after any `pyproject.toml`/
`uv.lock` change and commit the regenerated file alongside it. The target runs
`uv export` (pinned to `uv.lock`, `--no-emit-project` so the export lists only
third-party dependencies, not ember's own package) and then
`scripts/freeze_deployment_requirements.py`, which (1) resolves every PEP 508
environment marker (e.g. `; sys_platform == 'linux'`) against the Outerbounds
deployment's actual target (Linux x86_64, CPython 3.12) and drops non-matching
lines (Windows/emscripten-only packages) — Outerbounds' Fast Bakery
requirements parser rejects markers outright, unlike `pip` — and (2) re-adds
an explicit `ember-advise==<version>` line, pinned to the version in this
checkout's `pyproject.toml`, because Fast Bakery only `pip install`s what this
file lists and does not install the packaged source tree it copies in via
`--package-src-path .` (without that line, `ember serve` in `commands:` fails
with `ember: command not found`).

**That pin must already be published on PyPI before you deploy** — if you've
bumped `pyproject.toml`'s version locally but haven't released it yet (see
"Lifecycle commands" in `AGENTS.md`), either deploy against the last
*released* version, or cut the release first (`make release-ember`) and
re-run `make deployment-requirements` against the released checkout; Fast
Bakery's `pip install -r requirements.txt` will fail to resolve a version
that isn't on PyPI yet.
