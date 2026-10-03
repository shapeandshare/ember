# Compatibility

This document records what ember has been tested against, and the known limits. Update it
when testing a new model revision, dependency series, or device.

**Last verified**: 2026-10-03 on macOS on Apple Silicon (M4 Max, 128 GB).

## Tested models

| Model | Registry key | HF repository | Parameters | On disk | Modality | License | Pinned revision | Verified |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Clef-Flash | `flash` | Cloudflare/clef-flash | 9B | about 18 GiB | Text and vision | Apache-2.0 | `17f0b0ad...` | Yes, locally |
| Clef | `full` | Cloudflare/clef | 27B | about 55 GiB | Text and vision | Apache-2.0 | `2f3de3dd...` | Not locally |

Registry keys live in `ember/models.py` (`REGISTRY`). Select a model with `EMBER_MODEL`, or
pull the weights with `ember model pull`.

> **Warning:** `full` (27B) is pinned but not verified on this hardware. Expect a longer
> load and much larger memory use. The 8 GiB self-hosted CI runners cannot hold it, and the
> ~19 GB fp16 `flash` model does not fit the hosted runners either, so model-backed tests
> run locally only.

## Hardware requirements

ember runs Cloudflare's Clef model on Apple Silicon. The model has to fit in unified memory,
and that is the binding constraint — not CPU speed.

| Model | Parameters | On disk (fp16) | Weight in memory | Unified memory | Verified |
| --- | --- | --- | --- | --- | --- |
| `flash` | 9B | about 18 GiB | float16 | 32 GB or more | 128 GB (M4 Max) |
| `full` | 27B | about 55 GiB | float16 | 64 GB or more | not yet |

- **Apple Silicon Mac (M-series) on macOS**, arm64. Intel Macs and NVIDIA/CUDA are out of
  scope (Article VI).
- **Unified memory** must exceed the weights with headroom for activations and the KV cache.
  An 8 GiB host fails to load `flash` with an MPS out-of-memory error at the ~9 GiB allocator
  cap. 32 GB or more is the practical floor for `flash`.
- **Disk**: the weights above in Hugging Face's shared cache, plus a few GiB for the app and
  cache metadata.
- **Python 3.12** (uv); no other runtime.
- More GPU cores (Max, Ultra) load and answer faster; the same memory rule applies.

## Running in the cloud

ember is Apple-Silicon-first, so cloud means one of:

- **An Apple Silicon host** (a cloud Mac) with the unified memory above. This is the tested
  MPS path.
- **Any host via the CPU fallback**, with `EMBER_DEVICE=cpu`. It loads in float32, so plan for
  roughly twice the memory (`flash` about 36 GiB, `full` about 110 GiB) and much slower
  inference. Image and video inputs are expected to work, only slower.
- **NVIDIA/CUDA is out of scope** (Article VI). On a CUDA host, ember falls back to CPU.

Two cloud caveats:

- **The model server has no authentication and binds to `127.0.0.1`.** Exposing it beyond the
  host is outside the supported threat model; add your own access controls — a private
  network, an authenticating reverse proxy, or a firewall — if you do. See
  [`SECURITY.md`](SECURITY.md).
- **Inference stays local by design.** In the cloud, "local" is the host you provide: nothing
  in ember sends `state`, questions, or answers to shapeandshare. The privacy note in
  [`RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md) then applies to that host, including its logs.

## Tested stack

| Component | Version | Notes |
| --- | --- | --- |
| macOS | Apple Silicon (arm64) | Intel and CUDA are out of scope |
| Python | 3.12 | managed by uv (`.python-version`) |
| torch | 2.14.1 | MPS backend, float16; float32 on CPU |
| torchvision | 0.29.1 | required by the Clef image processor |
| transformers | 5.18.0 | model and processor |
| mcp | 2.3.0 | MCP stdio server |
| fastapi | 0.142.2 | model server HTTP API |
| uvicorn | 0.54.0 | ASGI server |

torch and torchvision are pinned to the tested minor series because MPS behavior is
version-sensitive. Widening the range is a constitution-governed change.

## Capability matrix

| Capability | MPS (default) | CPU (`EMBER_DEVICE=cpu`) |
| --- | --- | --- |
| Text advice | Verified, float16 | Verified, float32 |
| Image inputs | Verified | Expected, slower |
| Video frame inputs | Verified | Expected, slower |

Observed on the tested hardware: model load in about 5 seconds, and a warm request in
about 0.9 to 1.3 seconds for 220 to 360 input tokens.

## Known issues

- **Gated DeltaNet fallback.** Qwen3.5's hybrid linear attention has no optimized kernels
  for Apple Silicon, so it runs the pure-PyTorch path. Two "falling back" log lines are
  expected. The result is correct, only slower.
- **`device_map={"": "mps"}` segfaults.** The loader loads on CPU and then moves the module
  to MPS. Do not pass a device map.
- **Media must be inline.** `images` and `videos` accept base64 `data:` URIs or
  `{content_type, base64}` objects. Remote URLs and local paths are rejected by design, so
  an agent cannot make the server read host files or fetch URLs.
- **Numerics differ across devices.** MPS can differ from CPU and CUDA. Cross-check with
  `EMBER_DEVICE=cpu ember restart` when calibrated probabilities matter.
- **Context length.** `max_length` defaults to the model maximum (262144, from the pinned
  `config.json`). A value of `0` derives it. It is not a fixed 16384 cap.

See also: [`README.md`](README.md) for install steps, and
[`RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md) for what the numbers mean.
