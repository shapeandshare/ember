---
description: Run the mechanical vault audit (frontmatter, tag vocabulary and cardinality, wikilinks, code-refs, orphans) and fix what it finds.
---

# Vault health

## User input

```text
$ARGUMENTS
```

An argument names another vault directory (default: `vault/`).

## Execution

1. Run the audit:

   ```bash
   make vault-audit
   ```

   Or run it directly: `.venv/bin/python scripts/vault_audit.py vault`. Each finding
   prints as `<rule>: <note>: <detail>`.

2. Fix each finding by rule:
   - `frontmatter`: add or correct `title`, `type`, `tags`, `created`, and `updated`
     (see `vault/_meta/tags.md` and constitution Article IX).
   - `unknown-tag`: use a tag from `vault/_meta/tags.md`, or add the tag there first on
     purpose, then use it.
   - `tag-cardinality`: keep exactly one `type/*`, at least one `domain/*`, and at most
     one `status/*` tag.
   - `type-mismatch`: make the `type/*` tag match the `type` field.
   - `broken-wikilink`: fix the link or write the missing note. Never drop the
     reference silently.
   - `broken-code-ref`: point the ref at the moved or renamed file. If the code is gone,
     tag the note `status/stale` or `status/superseded` and say why.
   - `orphan`: link the note from `vault/ember.md` or from another reachable note. Don't
     weaken the check.
   - `missing-hub`: restore `vault/ember.md`.
3. If the audit itself is wrong, fix `scripts/vault_audit.py` and its tests in
   `tests/test_vault_audit.py`, not just the note.
4. Report the finding counts before and after, what you fixed, and anything left with
   the reason.

## Rules

- Never set `status/canonical`; only a human promotes a note to it.
- Never prune `vault/sessions/`; session logs are append-only.
