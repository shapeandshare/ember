# Compatibility

This document records what ember has been tested against, and the known limits. Update it
when testing a new model revision, dependency series, or device.

**Last verified**: 2026-10-03 on macOS on Apple Silicon (M4 Max, 128 GB).

## Tested models

| Model | Registry key | Source | Parameters | On disk | Modality | License | Revision | Verified |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Clef-Flash | `flash` | Cloudflare/clef-flash (Hugging Face Hub) | 9B | about 18 GiB | Text and vision | Apache-2.0 | `17f0b0ad...` | Yes, locally |
| Clef | `full` | Cloudflare/clef (Hugging Face Hub) | 27B | about 55 GiB | Text and vision | Apache-2.0 | `2f3de3dd...` | Not locally |

Registry keys live in `ember/models.py` (`REGISTRY`). Select a model with `EMBER_MODEL`, or
pull the weights with `ember model pull`. `flash` is the default registry entry. ember does
not verify downloaded weights against a hash (constitution Article V, "Model Loading") — it
supports any model that fits its loader contract, not a hand-maintained allowlist of
individually pinned, hash-verified weights.

A hosted deployment (e.g. Outerbounds) that supplies the model's location directly at start
time via `EMBER_MODEL_S3_URI` doesn't use this registry at all — see README.md "Hosted
deployment: a model location supplied at start time." AWS credentials
(`EMBER_S3_ACCESS_KEY_ID`/`_SECRET_ACCESS_KEY`, see README.md) for that path are
optional — boto3's default credential chain (an attached IAM role, e.g. on Outerbounds; env
vars; `~/.aws/credentials`) applies when they are unset.

> **Warning:** `full` (27B) is not verified on this hardware. Expect a longer load and much
> larger memory use. The 8 GiB self-hosted CI runners cannot hold it, and the ~19 GB fp16
> `flash` model does not fit the hosted runners either, so model-backed tests run locally
> only.

## Hardware requirements

ember runs decision models (currently Cloudflare's Clef) on Apple Silicon. The model has to
fit in unified memory, and that is the binding constraint — not CPU speed.

| Model | Parameters | On disk (fp16) | Weight in memory | Unified memory | Verified |
| --- | --- | --- | --- | --- | --- |
| `flash` | 9B | about 18 GiB | float16 | 32 GB or more | 128 GB (M4 Max) |
| `full` | 27B | about 55 GiB | float16 | 64 GB or more | not yet |

- **Apple Silicon Mac (M-series) on macOS**, arm64, for local use (MPS). Intel Macs remain
  out of scope. NVIDIA GPUs (CUDA) are supported for hosted deployment (Article VI, "Apple
  Silicon and CUDA") — see "Running in the cloud" below.
- **Unified memory** must exceed the weights with headroom for activations and the KV cache.
  An 8 GiB host fails to load `flash` with an MPS out-of-memory error at the ~9 GiB allocator
  cap. 32 GB or more is the practical floor for `flash`.
- **Disk**: the weights above in Hugging Face's shared cache, plus a few GiB for the app and
  cache metadata.
- **Python 3.12** (uv); no other runtime.
- More GPU cores (Max, Ultra) load and answer faster; the same memory rule applies.

## Running in the cloud

ember is Apple-Silicon-first locally and supports NVIDIA GPUs for hosted deployment
(constitution Article VI, "Apple Silicon and CUDA"). Cloud means one of:

- **An Apple Silicon host** (a cloud Mac) with the unified memory above. This is the tested
  MPS path.
- **An NVIDIA GPU host**, with `EMBER_DEVICE=cuda` — float16, matching MPS's memory/dtype
  rules (not the CPU float32 numbers below). This is the hosted-deployment path (e.g.
  Outerbounds compute, which is Linux and has no MPS); see `deployment/README.md` for a
  full example. Not yet verified against real NVIDIA hardware — see "Tested stack" below.
- **Any host via the CPU fallback**, with `EMBER_DEVICE=cpu`. It loads in float32, so plan for
  roughly twice the memory (`flash` about 36 GiB, `full` about 110 GiB) and much slower
  inference. Image and video inputs are expected to work, only slower.

Two cloud caveats:

- **The model server binds to `127.0.0.1` by default with no authentication.** To serve
  remote clients, set `EMBER_HOST` and `EMBER_SERVER_AUTH_TOKEN` (then `/v1/systemone`
  requires `Authorization: Bearer <token>`; `/health` and `/metrics` stay open). Ember does
  not terminate TLS — front it with an authenticating reverse proxy. If you leave
  `EMBER_SERVER_AUTH_TOKEN` unset and expose the host, you are responsible for access control
  (private network or firewall). See [`SECURITY.md`](SECURITY.md).
- **Inference runs where you point it.** By default that is your host: nothing in ember sends
  `state`, questions, or answers to shapeandshare. If you configure a remote endpoint
  (`EMBER_SERVER_URL`), state is sent to that endpoint — the privacy note in
  [`RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md) then applies to that host, including its logs.
- **A deployment platform (e.g. Outerbounds) can supply the model's S3 location directly at
  start time** via `EMBER_MODEL_S3_URI`, instead of selecting a `REGISTRY` entry — ember
  supports any model that fits its loader contract (constitution Article V, "Model Loading"),
  not a hand-maintained allowlist of individually pinned, hash-verified weights. See
  README.md "Hosted deployment: a model location supplied at start time."

## Tested stack

| Component | Version | Notes |
| --- | --- | --- |
| macOS | Apple Silicon (arm64) | Local use (MPS); Intel is out of scope |
| Linux | x86_64 / aarch64 | Hosted deployment (CUDA); `torch`'s default PyPI wheel already bundles CUDA support here, no special index needed |
| Python | 3.12 | managed by uv (`.python-version`) |
| torch | 2.14.1 | MPS/CUDA backend, float16; float32 on CPU |
| torchvision | 0.29.1 | required by the Clef image processor |
| transformers | 5.18.0 | model and processor |
| mcp | 2.3.0 | MCP stdio server |
| fastapi | 0.142.2 | model server HTTP API |
| uvicorn | 0.54.0 | ASGI server |

torch and torchvision are pinned to the tested minor series because MPS behavior is
version-sensitive. Widening the range is a constitution-governed change. CUDA support has
not yet been exercised against real NVIDIA hardware — the code path is implemented and unit
tested (`ember/serving/runtime.py::pick_device`/`pick_dtype`), but no model-backed run on a
CUDA host has been recorded here yet. Update this note once one has.

## Capability matrix

| Capability | MPS (default) | CUDA (`EMBER_DEVICE=cuda`) | CPU (`EMBER_DEVICE=cpu`) |
| --- | --- | --- | --- |
| Text advice | Verified, float16 | Not yet verified, float16 | Verified, float32 |
| Image inputs | Verified | Expected, not yet verified | Expected, slower |
| Video frame inputs | Verified | Expected, not yet verified | Expected, slower |

Observed on the tested hardware: model load in about 5 seconds, and a warm request in
about 0.9 to 1.3 seconds for 220 to 360 input tokens. Counting the full request before
inference adds about 0.4 ms to a warm 153-token request (about 0.65 seconds end to end),
under 0.1%.

## Known issues

- **Gated DeltaNet fallback.** Qwen3.5's hybrid linear attention has no optimized kernels
  for Apple Silicon, so it runs the pure-PyTorch path. Two "falling back" log lines are
  expected. The result is correct, only slower.
- **`device_map={"": "mps"}` segfaults.** The loader loads on CPU and then moves the module
  to the target device (MPS or CUDA). Do not pass a device map directly — this constraint is
  MPS-specific; CUDA has no equivalent issue but shares the same CPU-then-move code path
  (constitution Article XV, simplest viable solution).
- **Media must be inline.** `images` and `videos` accept base64 `data:` URIs or
  `{content_type, base64}` objects. Remote URLs and local paths are rejected by design, so
  an agent cannot make the server read host files or fetch URLs.
- **Numerics differ across devices.** MPS can differ from CPU and CUDA. Cross-check with
  `EMBER_DEVICE=cpu ember restart` when calibrated probabilities matter.
- **Context length.** The effective maximum is 262,144 tokens, declared by both models'
  `config.json` (`EMBER_MAX_LENGTH=0` derives it; it is not a fixed 16384 cap). Each
  request is also held to a per-model cap (`EMBER_MAX_REQUEST_LENGTH`). Until the
  long-context probe (`make eval-context`, MPS on an M4 Max with 128 GB) measures a model,
  its default is its own fallback, the longest probe length whose peak memory leaves at
  least 4 GiB of its budget free for the OS: 24,576 tokens for `flash` (27.83 GiB of
  32 GiB; 32,768 peaked at 32.35 GiB) and 8,192 for `full` (59.54 GiB of 64 GiB; 16,384
  peaked at 63.54 GiB). A model outside the registry gets the lowest registry cap. The
  measured values and the probe run ID replace
  the fallbacks. The whole encoded request counts, including questions, schema, the prompt
  wrapper, and media, so image-heavy requests near the cap that passed the earlier
  state-only check may now be refused. An oversized request is refused with a 413 that
  states its token split, never truncated. The caps hold for the pinned model revisions
  and are re-measured whenever a revision changes. `0` disables the cap; the effective
  maximum still applies.

See also: [`README.md`](README.md) for install steps, and
[`RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md) for what the numbers mean.
