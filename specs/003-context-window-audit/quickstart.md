# Quickstart: Validate the Context Window Audit

**Feature**: `003-context-window-audit` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Each step gives a command and what you should see. Formats are defined in
[contracts/](./contracts/), and field definitions are in [data-model.md](./data-model.md).

## Prerequisites

- An Apple Silicon Mac with at least 32 GB of memory for flash, or 64 GB for full. The
  reference machine is an M4 Max with 128 GB.
- Dependencies and the pinned flash weights: `make bootstrap`.
- The full model, which the probe also needs: `ember model pull full`.
- Before running the probe, stop any warm server you don't need (`ember stop`). The probe
  loads its own copy of each model.

## 1. Fast gates (no model)

```bash
make check
make pr-ready
make test-cov
```

All three pass, and coverage stays at or above 81%.

## 2. Model-backed tests

```bash
make test-strict
```

The new tests pass:
- For dict, string, and image fixtures, the counted total equals
  `len(encode_record(...).input_ids)` (zero drift).
- A known-length state encodes to its expected count (FR-003).
- A request exactly at the limit is served; one token more is refused.
- With the cap disabled and `EMBER_MAX_LENGTH` reduced, over-limit requests are refused.
- On every served response, `usage.input_tokens` equals the counted total.
- A state of about 1M tokens is refused quickly, without a crash.

## 3. Limits are visible (US1)

```bash
ember start
curl -s http://127.0.0.1:8765/health | jq .engine
ember logs | grep "limits:"
ember doctor | grep limits
```

Expected:
- `engine` shows `max_length`, `max_length_source`, `max_request_length`, and
  `max_request_length_source` ([http-api.md](./contracts/http-api.md)).
- The log has one `limits:` line from model load.
- doctor prints `[info] limits: enforced 32768 tokens; …; live from local server`. Until
  the probe has run, it shows `max_request_length 32768 (fallback)`.

```bash
ember stop && ember doctor | grep limits
```

Expected: the same numbers, labeled `configured, server not running`.

```bash
EMBER_SERVER_URL=https://ember.invalid ember doctor | grep limits
```

Expected: `[info] limits: unknown; remote endpoint unreachable`. Use a non-loopback host:
ember treats any loopback URL, `https://127.0.0.1:9` included, as the local endpoint, so
doctor would show the configured values instead.

## 4. Refusals are explicit and actionable (US2)

```bash
EMBER_MAX_REQUEST_LENGTH=1024 ember restart
python3 - <<'EOF'
import httpx
r = httpx.post("http://127.0.0.1:8765/v1/systemone", timeout=60, json={
    "state": "log line\n" * 900,
    "questions": {"retry": {"type": "noul", "instructions": "Is it safe to retry?"}},
})
print(r.status_code, r.json()["detail"])
EOF
```

Expected:
- `413 request too large: … exceeds the 1024-token per-request cap
  (EMBER_MAX_REQUEST_LENGTH). Split: state …, media 0, fixed overhead … `
  ([http-api.md](./contracts/http-api.md)).
- state + media + fixed equals the total.

Two variations on the same request:
- **Model maximum**: restart with `EMBER_MAX_REQUEST_LENGTH=0 EMBER_MAX_LENGTH=1024`. The
  refusal names the `maximum length (EMBER_MAX_LENGTH)`.
- **Media**: send a small state plus a large PNG in `images`. The split shows media as the
  largest part.

Through MCP, with the same settings: run `make mcp-check`, or call `advise` from an agent
with an oversized state. The tool error reads `ember server error 413: request too large: …`
with the split intact ([mcp-tool.md](./contracts/mcp-tool.md)).

Restore the defaults with `ember restart`.

## 5. Agent guidance (US4)

```bash
ember agents show instructions | wc -c
diff ember/agent_kit/ember-advise/SKILL.md packages/claude-plugin/skills/ember-advise/SKILL.md
```

Expected:
- `wc` prints 2048 or less.
- `diff` prints nothing.
- The instructions, skill, and snippet state the refusal behavior and the current default
  ([agent-kit.md](./contracts/agent-kit.md)).

## 6. Probe pipeline (US3)

```bash
make eval-context-smoke
ls results/context/
ember eval context --rescore <run_id> && shasum results/context/<run_id>/summary.json
```

Expected:
- The smoke run finishes in minutes and writes `manifest.json`, `rows-flash.jsonl`, and
  `summary.json` ([eval-context.md](./contracts/eval-context.md)).
- Rescoring leaves `summary.json`'s checksum unchanged.
- In `rows-flash.jsonl`, `rss_start_bytes` is at most 25% of flash's weights (about
  4.5 GiB), and the 2K `driver_peak_bytes` is 0.9–1.5× the weights (research R11). If
  either check fails, stop: peak memory is being double-counted.

```bash
ember eval context --pilot
```

Prints the projected 95% half-width at the included item count.
- **Exit 0**: the sizing gate passed.
- **Exit 2**: the items can't resolve the 2-point tolerance. Stop and decide with a human.

## 7. Choose the caps (US3; takes hours to days, resumable)

```bash
make eval-context                                    # if interrupted: ember eval context --resume <run_id>
ember eval context --reproduce <run_id> --items 24   # spot-check reproducibility (compares rows only)
ember eval context --snapshot <run_id>
```

Then finish the change:
1. Set `max_request_length` for `flash` and `full` in `REGISTRY` (`ember/models.py`) to
   each model's cap in `summary.json`.
2. Write the vault decision that supersedes D-002, citing the snapshot.
3. Update the STRIDE D-002 entries.
4. Update README, COMPATIBILITY.md, and the kit numbers.
5. Run `make test` again. The kit-numbers test passes only when the text matches the
   registry.
