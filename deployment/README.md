# Deploying ember to Outerbounds

Deploy ember's model server itself (not a client) to Outerbounds, so an agent
elsewhere can reach it over `EMBER_SERVER_URL`. This mirrors
[`model-foundry`](https://github.com/anaconda/model-foundry)'s own
[Outerbounds App](https://docs.outerbounds.com/) deployment contract.

## What this deploys

`ember serve` in the foreground, as a FastAPI/uvicorn app, loading a model from
an `s3://bucket/prefix` location (`EMBER_MODEL_S3_URI`) rather than a pinned
`REGISTRY` entry — there is no Hugging Face download at deploy time. See
`ember/serving/hosted.py` and README.md's "Hosted deployment: a model location
supplied at start time" for the mechanism, and constitution Article V ("Model
Loading") for why no integrity hash is checked against that location.

## Prerequisites

1. **A GPU-backed compute pool** (Outerbounds UI → Compute) for the CUDA path
   in `deploy.yaml` (constitution Article VI, "Apple Silicon and CUDA" — CUDA
   is the hosted-deployment device; MPS is Apple-Silicon-only and unavailable
   on Outerbounds' Linux compute). A CPU-only pool works too — see "CPU-only
   deployment" below.
2. **An S3 bucket containing the model's files** (`config.json`,
   `joint_schema_model.py`, `joint_head.safetensors`,
   `joint_head_config.json`, `model.safetensors.index.json`, and the
   sharded `model-*.safetensors` weight files — the same shape
   `ember/models.py` downloads for `flash`/`full` from Hugging Face).
3. **A secret integration** (named to match your org's `{repo}-{environment}`
   convention) holding:
   - `EMBER_SERVER_AUTH_TOKEN` — the API key/bearer value remote clients must
     present. Required for any deployment reachable outside a fully trusted
     network — `/health` and `/metrics` stay open regardless.
   - `EMBER_ANACONDA_S3_ACCESS_KEY_ID` / `EMBER_ANACONDA_S3_SECRET_ACCESS_KEY`
     — **optional**. Omit entirely when the compute pool already has an IAM
     role with read access to the bucket; boto3's default credential chain
     picks it up automatically (see
     `vault/decisions/2026-10-08-optional-s3-credentials-iam-role.md`). Set
     both only if no role is attached.
4. **Outerbounds CLI configured** and authenticated against your workspace.

## Deploy

```sh
# Regenerate requirements.txt from uv.lock — do this before every deploy so
# Fast Bakery resolves the exact dependency set CI/tests ran against.
make deployment-requirements

# Fill in deployment/deploy.yaml's <CONFIRM>/<your-...> placeholders first
# (compute pool name, bucket/prefix, team/owner tags, secret integration name),
# then:
outerbounds app deploy \
  --config-file deployment/deploy.yaml \
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
prints, or your `generate_static_url: true` stable URL):

```sh
ember init --opencode --server-url https://<your-app>.outerbounds.app --auth-header x-api-key
export EMBER_AUTH_TOKEN=<the same value as EMBER_SERVER_AUTH_TOKEN above>
```

`EMBER_AUTH_TOKEN` is **never** written to `opencode.json`/`kilo.json`/the
plugin file — export it in the shell that launches the agent (see README.md
"Remote inference"). `--auth-header` accepts any header name; `x-api-key` is
sent verbatim, `Authorization` (the default) is sent as `Bearer <token>`.

## Choosing the model and sizing GPU memory

There is no runtime VRAM-limiting knob (no quantization, no multi-GPU sharding, no
`max_memory` ceiling) — ember always loads the full model in float16 on a single
device. **Size the GPU to the model, not the other way around**: pick
`resources.gpu`/the compute pool first, by checking your model against the
numbers in [`COMPATIBILITY.md`](../COMPATIBILITY.md#hardware-requirements)
(`flash` 9B needs roughly 18 GiB of weights plus activation/KV-cache headroom —
32 GB+ total is the practical floor on MPS and a reasonable floor on CUDA too;
`full` 27B needs roughly 55 GiB, 64 GB+ total). An undersized GPU fails with a
CUDA out-of-memory error at load time, not a graceful degradation.

Three independent settings control what actually loads and how much memory it
needs:

| Setting | Controls | Example |
| --- | --- | --- |
| `EMBER_MODEL_S3_URI` (or `EMBER_MODEL` for a `REGISTRY` entry) | **Which model** — this is what actually determines the VRAM requirement | `s3://my-bucket/clef-flash` (9B) vs. a `full`-sized (27B) location |
| `EMBER_DEVICE` | **Which accelerator** — `cuda`/`mps` load in float16 (smaller footprint); `cpu` loads in float32 (~2x the memory, see "CPU-only deployment" below) | `cuda` |
| `resources.gpu` / `compute_pools` in `deploy.yaml` | **How much VRAM is actually available** — this is capacity planning, not a software setting; pick a pool whose GPU memory exceeds the chosen model's float16 footprint with headroom | a pool with 24–40 GB+ VRAM for `flash` |

`EMBER_MAX_LENGTH`/`EMBER_MAX_REQUEST_LENGTH` (see README.md's env var table) bound
context length, which indirectly affects KV-cache memory at long contexts, but
they are not a VRAM ceiling — they do not prevent an OOM if the base model
itself doesn't fit.

## CPU-only deployment

No GPU compute pool yet? Edit `deploy.yaml`:

- `EMBER_DEVICE: "cpu"` instead of `"cuda"`.
- Remove `resources.gpu` and roughly double `resources.memory` (CPU loads in
  float32, about 2x the float16 footprint — see COMPATIBILITY.md).
- Point `compute_pools` at a CPU pool instead.

## Updating dependencies

`deployment/requirements.txt` is generated, not hand-maintained — never edit
it directly. Run `make deployment-requirements` after any `pyproject.toml`/
`uv.lock` change and commit the regenerated file alongside it.
