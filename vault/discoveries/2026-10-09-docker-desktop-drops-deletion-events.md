---
title: "Docker Desktop drops host deletions, so the site preview polls"
type: discovery
tags:
  - type/discovery
  - domain/tooling
  - status/draft
created: "2026-10-09"
updated: "2026-10-09"
code-refs:
  - shared/site.mk
  - scripts/build_site_docs.py
  - site/_config.yml
---

# Docker Desktop drops host deletions, so the site preview polls

Part of [[ember]]. `make site-serve` runs `jekyll serve` in Docker with `site/` bind-mounted
(see [[2026-10-03-publish-a-pages-site]]). Under Docker Desktop, Jekyll's event-based watcher
sees host files created or edited, never sees one deleted, and never sees the documents the
site publishes from outside `site/`.

## What was tested

On Docker Desktop (Docker Engine 29.8, macOS, Apple Silicon), Jekyll 4.4.1, Listen 3.10.1:

- Plain `jekyll serve`: a new file under `site/` was served in about 3 s and an edit to it in
  about 2 s. Deleting it triggered no rebuild within 20 s and the file stayed served (HTTP 200).
  This happened twice, the second time with no other rebuild nearby.
- Editing `README.md` changed nothing: only `site/` is mounted, and
  `scripts/build_site_docs.py` copied the documents once, at startup.
- With `--force_polling`, the `build_site_docs.py --watch` host watcher, and `--livereload`
  (port 35729 published): the deletion was picked up in about 2 s, and a `README.md` edit
  reached an open `/docs/overview/` page in headless Chromium in about 2.8 s through a
  LiveReload reload, with no console errors. The idle container used about 1% CPU.

## Finding

- Host-side deletions on a Docker Desktop bind mount do not reach the container's inotify
  watchers; creations and modifications do. Polling works because it rescans the mount.
- Jekyll watches only its source directory, so documents copied in from the repository need
  a host-side watcher to stay current.
- Polling rescans every file Jekyll does not exclude. jekyll-watch turns `exclude` entries
  into Listen ignore patterns, and Listen skips a silenced directory without scanning it,
  so `site/_config.yml` excludes the ~2,800-file gem cache in `site/.gems`.

## Relevance

- Keep `--force_polling` in `make site-serve`; without it a deleted or renamed page stays
  served until the preview restarts.
- A new published document only needs a manifest entry: the watcher derives what it watches
  from `site/_data/docs.json`.
- The benchmark pages (`scripts/build_site_benchmark.py`) are still built once, at startup.

## References

- `shared/site.mk` (`site-serve`), `scripts/build_site_docs.py` (`watch`),
  `tests/test_build_site_docs.py`
- jekyll-watch 2.2.1 `listen_ignore_paths`; Listen 3.10.1 `Change#invalidate`
