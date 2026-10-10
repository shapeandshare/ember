# Contract: CLI (`ember doctor` limits line, `ember eval context`)

**Feature**: `003-context-window-audit`
**Date**: 2026-10-09

## `ember doctor`: the limits line

Doctor prints one informational line after the `endpoint` line. It never changes doctor's
exit code.

```
[info] limits: enforced {E} tokens; max_length {M} ({src}), max_request_length {C} ({src}); {provenance}
```

- `{C}` is a number, or `disabled` when the cap is `0`.
- `{src}` is a `LimitSource` value: `model`, `fallback`, `operator`, or `measured`.

| Situation | Output |
|-----------|--------|
| A local server answers `/health` with limit fields | `{provenance}` is `live from local server` |
| A remote endpoint answers `/health` with limit fields | `{provenance}` is `live from <endpoint url>` |
| Local endpoint, no server running | `{provenance}` is `configured, server not running` |
| Remote endpoint unreachable | the whole line is `[info] limits: unknown; remote endpoint unreachable` |
| Server reachable, but no model is loaded yet (`engine` is `null`) | the whole line is `[info] limits: unknown; the server has not loaded a model yet` |
| Server reachable but sends no limit fields (an older ember) | the whole line is `[info] limits: unknown; the server does not report limits (older ember)` |

**Configured values**:
- They come from the same resolver the server uses ([config.md](./config.md)), applied to
  the selected model's directory.
- A model that isn't pulled yet gives `max_length 32768 (fallback)`.
- Doctor never imports torch.

## `ember eval context`

`ember eval context` runs only in a checkout, because `evals/` isn't packaged. Outside a
checkout it prints the existing checkout error and exits 1.

```
ember eval context [--models flash,full] [--lengths 2048,4096,...] [--items N]
                   [--run-id ID] [--resume ID] [--pilot] [--smoke]
                   [--rescore ID] [--reproduce ID] [--snapshot ID]
```

| Flag | Effect |
|------|--------|
| (none) | Full run: the pilot sizing gate, then flash and full, each in its own worker process. Writes `results/context/<run_id>/` |
| `--models` | Run a subset of the registered models (default: all registered) |
| `--lengths` | Run a subset of the seven lengths. 2048 is always included as the baseline |
| `--items N` | Run only the first N items, in manifest order. For debugging; the run is marked non-canonical. With `--reproduce`, re-runs only those items and compares rows only |
| `--run-id ID` | Name the run (default `context_<UTC timestamp>`) |
| `--resume ID` | Continue an interrupted run, skipping rows already finished |
| `--pilot` | Stop after the sizing gate and print the projected half-width |
| `--smoke` | flash only, lengths 2048 and 4096, 3 items, 3 depths. Takes minutes; non-canonical |
| `--rescore ID` | Rebuild `summary.json` from the rows and manifest. The output is byte-identical for the same inputs |
| `--reproduce ID` | Re-run ID's pinned inputs into a new run and compare the two ([eval-context.md](./eval-context.md)) |
| `--snapshot ID` | Copy a completed canonical run whose sizing gate passed into the tracked `evals/context/runs/ID/`, with its dataset; refuses any other run |

**Exit codes**:

| Code | Meaning |
|------|---------|
| `0` | Done, whatever the verdict |
| `1` | Error, including no MPS device (the probe measures MPS only) |
| `2` | The sizing gate failed, or `--reproduce` found a mismatch |

**Output**: Progress goes to stderr. When the run finishes, it prints one line per model,
for example `flash: cap 24576 (first failure at 32768: memory)`.

## Make targets (`shared/testing.mk`)

| Target | Recipe |
|--------|--------|
| `eval-context` | `$(PY) evals/context/run_context.py` |
| `eval-context-smoke` | `$(PY) evals/context/run_context.py --smoke` |
