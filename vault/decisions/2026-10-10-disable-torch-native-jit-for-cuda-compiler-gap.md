---
title: "Disable torch._native's Triton JIT by default (EMBER_TORCH_DISABLE_NATIVE_JIT)"
type: decision
tags:
  - type/decision
  - domain/runtime
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - ember/serving/runtime.py
  - tests/test_runtime_unit.py
  - deployment/flash.yaml
  - README.md
  - COMPATIBILITY.md
---

# Disable torch._native's Triton JIT by default (EMBER_TORCH_DISABLE_NATIVE_JIT)

Part of [[ember]]. Every real inference request to the live Outerbounds CUDA deployment
([[2026-10-10-remove-t004-non-loopback-auth-check]]) failed with HTTP 500 — the first
end-to-end CUDA test of the deployment that was previously blocked by two earlier bugs this
session. Root cause: torch 2.14's new `torch._native` registry JIT-compiles a Triton kernel
on first use for a specific `aten::bmm` outer-product shape (hit by Qwen3.5's RoPE forward
pass), and Outerbounds' Fast Bakery base image has no C compiler — with no supported way to
install one through `deployment/deploy.yaml`'s contract (Python `requirements.txt` only, no
system/apt packages).

## Context

`/health` reported `{"status": "ok"}` throughout — the model loaded correctly onto the GPU.
Only a real `/v1/systemone` call surfaced the failure, confirming it's specifically a
first-use JIT path, not a load-time problem. Server logs (`uv run outerbounds app logs`)
showed the full traceback: `transformers/models/qwen3_5/modeling_qwen3_5.py`'s RoPE
`forward()` → `torch._native/registry.py`'s `eager_router` → `torch._native/ops/
bmm_outer_product/triton_impl.py` → Triton's own JIT compiler → `RuntimeError: Failed to
find C compiler`.

Traced the registration mechanism: `ember/.venv/lib/python3.12/site-packages/torch/_native/
ops/bmm_outer_product/__init__.py` calls `register_to_dispatch()` at import time
(`triton_impl.py`), which registers an override for `aten::bmm` on the `CUDA` dispatch key
whenever the input shapes match an outer-product pattern — this always happens on any CUDA
build with Triton installed (both true in ember's pinned `torch==2.14.1`/`triton` deps),
regardless of whether a compiler is actually available to realize the kernel. The failure is
deferred until the override's condition function matches a real tensor shape at inference
time, which is why `/health`'s trivial startup path never exercises it.

Found `torch._native.common_utils.check_native_jit_disabled()`: a single, already-shipped
kill switch — `TORCH_DISABLE_NATIVE_JIT=1` — checked by every DSL backend (Triton, CuteDSL,
Helion) before registering any override. Confirmed via `torch._native.triton_utils.
_check_runtime_available()` that this registration only ever happens on a CUDA build
(`_cuda.is_built()` gate) — the env var is always a safe no-op on MPS/CPU.

## Decision

- **`ember/serving/runtime.py`**: `os.environ.setdefault("TORCH_DISABLE_NATIVE_JIT", ...)`
  added immediately after the existing `PYTORCH_ENABLE_MPS_FALLBACK` line (same "must be set
  before torch's dispatch tables are built" constraint, same module-level-before-`import
  torch` pattern). Defaults to `"1"` (disabled) given a minimal CUDA deployment container
  without a compiler is the primary hosted-deployment target; reads
  `EMBER_TORCH_DISABLE_NATIVE_JIT` first so an operator with a working compiler toolchain can
  set it to `"0"` to opt back into the (likely faster) Triton path.
- **Correctness, not just availability**: disabling the override does not change what gets
  computed — `aten::bmm`'s standard eager/ATen implementation (a mature, cuBLAS-backed
  kernel) runs instead of the Triton-JIT'd one, for the exact same mathematical operation.
  This is a performance trade-off (unmeasured; the Triton path is a narrow optimization for
  one tensor shape, not a correctness-required path), not a correctness risk.
- **Tests (TDD)**: `tests/test_runtime_unit.py::test_runtime_import_sets_torch_disable_native_jit_before_torch_loads`
  and `::test_ember_torch_disable_native_jit_env_var_overrides_the_default` both use a fresh
  subprocess (matching the existing `test_mcp_server_import_does_not_load_torch` pattern) —
  `torch` is already imported in the test process by this same file's own module-level
  `import ember.serving.runtime as runtime`, so checking `os.environ` in-process would not
  prove the before-`import torch` ordering. Both subprocess calls explicitly strip
  `TORCH_DISABLE_NATIVE_JIT` from the inherited environment first — without that, the parent
  pytest process's own (already-set) value leaks into the child via `subprocess.run`'s
  default environment inheritance and defeats the test.
- **Documentation**: README.md's env var table and COMPATIBILITY.md's "Known issues" both
  describe the mechanism and the override.

## Consequences

- This is the fix most likely to unblock real inference on the Outerbounds deployment, but it
  has **not yet been verified end-to-end against the live CUDA host** at the time of writing
  this note — that is the next step (redeploy with this change, confirm a real
  `/v1/systemone` call succeeds). Update this note (or supersede it) once confirmed, including
  whether the eager fallback introduces any measurable latency regression on CUDA.
- `EMBER_TORCH_DISABLE_NATIVE_JIT=1` is now ember's default everywhere, not just on
  Outerbounds — any CUDA host without a compiler benefits automatically; a host with one and
  wanting the Triton path must explicitly opt back in.
- This is a new category of "missing CUDA toolchain" issue distinct from the existing
  documented MPS gaps (Gated DeltaNet's missing Apple-Silicon kernels, `causal_conv1d`/
  `flash-linear-attention`). Both are now recorded together in COMPATIBILITY.md's "Known
  issues" for a single place to look when a model op fails to find its optimized kernel.

## References

- [[2026-10-10-remove-t004-non-loopback-auth-check]] — the deployment this failure surfaced
  on, once T-004 and the missing `ember-advise` package were both already fixed.
- `torch/_native/common_utils.py::check_native_jit_disabled` — the upstream kill switch.
- `torch/_native/ops/bmm_outer_product/triton_impl.py` — the specific registered override
  that failed.
