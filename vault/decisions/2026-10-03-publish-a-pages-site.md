---
title: publish a Pages site
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/brand
  - status/draft
created: 2026-10-03
updated: 2026-10-03
code-refs:
  - site/_config.yml
  - site/_data/docs.json
  - scripts/build_site_docs.py
  - .github/workflows/deploy-site.yml
---

# publish a Pages site

Part of [[ember]]. The project publishes a Jekyll site to GitHub Pages at
`https://shapeandshare.github.io/ember/`, built by GitHub Actions from the
repository's own markdown and brand assets, following the same pattern as the
organisation's `oldgrowth` site.

## Context

- A survey of the sibling repositories found exactly one with Pages live: `oldgrowth`,
  a Jekyll 4.3 site in `site/` deployed by Actions
  (`configure-pages → jekyll build --baseurl → upload-pages-artifact → deploy-pages`,
  Pages `build_type: workflow`). `darkharbour` carries the org's written research
  (`specs/059-harbour-pages-site/research.md`): it chose Jekyll over MkDocs
  (unmaintained as of 2026; successor "Zensical" still settling), Hugo, and Astro, and
  it pins the project-page failure mode — no `baseurl` in config, pass it explicitly in
  CI, use `relative_url`. `gh-runner-standalone` hand-writes static HTML with no
  generator. No repo uses MkDocs, mdBook, or similar.
- ember needs landing, docs, and a benchmark page, and its brand lives in `assets/brand/`
  governed by `DESIGN.md` (system fonts, no CDN, `<picture>` for dark/light).

## Decision

- **Jekyll 4.3 in `site/`**, built and deployed by `.github/workflows/deploy-site.yml`
  using the standard Pages pipeline. Pages is set to `build_type: workflow`; the site is
  a project page under `/ember/`, so `baseurl` stays out of `_config.yml` (CI passes
  `--baseurl`, local builds pass `""`) and every internal link uses `relative_url`.
- **Content is assembled at build time.** `scripts/build_site_docs.py` reads a manifest
  (`site/_data/docs.json`) and copies the chosen repository documents into `site/_docs/`
  with front matter, rewriting links (published docs → their site URL, brand assets →
  `/assets`, everything else → its GitHub blob). It also copies the brand assets. Both
  outputs are gitignored, so the repository's markdown and `assets/brand/` remain the
  single source; publishing a page means adding a manifest entry.
- **Consistent with ember's hardening.** The deploy workflow starts from
  `permissions: {}` and grants per job, pins every action to a full commit SHA, disables
  the Ruby cache so zizmor's cache-poisoning audit stays clean, and uses `ruby/setup-ruby`
  (added to the Actions allow-list). `make site` / `make site-serve` build locally in a
  Ruby 3.3 container because the macOS system Ruby is too old for Jekyll 4.
- The benchmark reviewer report (a self-contained `report.html` from `ember eval export`)
  is committed at `site/results/index.html` and served at `/results/`.

## Consequences

- `site/_docs/` and `site/assets/brand/` are generated and MUST NOT be committed; the
  deploy workflow rebuilds them. `make site` needs Docker.
- The site adds `ruby/setup-ruby` to the Actions allow-list and five SHA-pinned actions to
  Dependabot's github-actions updates.
- No link-integrity gate yet; `darkharbour` uses `lychee` for that. Worth adding if the
  docs section grows.

## Benchmark data and rendering

The benchmark report is part of the same site. A run is snapshotted into the tracked
`benchmark/<run-id>/` (results, trace, dataset, and the `analysis.build` **model**) by
`scripts/snapshot_evals.py` (`make eval-snapshot` / `ember eval snapshot`) — everything up
to, but not including, HTML rendering. `scripts/build_site_benchmark.py` then renders that
model into native pages under `/results/` (one page per report section, inside the site
shell), reusing the report's content styles (`evals/report.css`) as the site asset
`benchmark.css`. The run produces the data; the website renders the HTML. `ember eval
export` still writes a portable single-file HTML for external reviewers, which the site no
longer uses.
