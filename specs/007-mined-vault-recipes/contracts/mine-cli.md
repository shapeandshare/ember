# Contract: `ember eval mine`

## Invocation

```bash
ember eval mine [--recipe NAME] [--source-dir PATH] [--dataset PATH] [--lock PATH]
```

- `--recipe` defaults to `tag_assignment`; an unknown name exits 2 and lists the known names.
- `--source-dir` defaults to `<repo root>/../oldgrowth`.
- `--dataset` defaults to `evals/clef-flash.jsonl`; `--lock` defaults to `evals/dataset/splits.lock`.
- Wired like `capture`/`context`: an argparse passthrough (`add_help=False` + `REMAINDER`) whose handler `cmd_eval_mine` lazy-imports `evals.dataset.mined.mine.main` — the command is checkout-only and raises the existing `_EVAL_CHECKOUT_ERROR` message when imported outside a clone.

## Behaviour

1. Resolve the source directory; confirm the pin exists (`git -C <dir> cat-file -e <pin>^{commit}`). Absent → refuse, naming the pin and the directory.
2. Confirm the grant is present in the source repository's committed `LICENSES.md` (read at HEAD; the working tree is never read). Absent → refuse, naming the missing grant (FR-012).
3. Snapshot the tree read-only at the pin; build the vocabulary; classify candidates; apply exclusions; sample; build items.
4. Write items through `write_items` (existing items preserved, new ones appended in id order); write the sampling manifest; extend `splits.lock` through `assign_new` + `append_lock`. Leave `register.json`, `versions.lock`, and the card untouched — the operator regenerates the card.
5. Print a summary: items written, exclusions by reason, the seed, and the source commit.

## Guarantees

- **Idempotent**: the same pin and seed produce identical bytes; running twice leaves `git status` clean.
- **Deterministic**: no wall-clock, no dictionary-order dependence, no RNG without the fixed seed.
- **Read-only** against the source repository; writes only this repo's dataset artifacts and the lock.
- **Offline**: no network, no model load.

## Exit codes

`0` success · `1` refusal or failure (missing grant, missing pin, missing source directory, a broken invariant) · `2` usage error.

## Non-goals

Does not run `card`/`check`/`lint`, does not score, does not touch `benchmark/`, does not commit.
