# Materials, provenance, and licensing

The machine-readable record is [provenance.json](provenance.json). Recorded on
**2026-10-02, America/Los_Angeles**. This is an evidence inventory, not a claim that
all upstream licensing, authorship, or rights have been conclusively audited.

## Coverage

The JSON inventories every PNG, SVG, saved prompt, CSS and HTML file under
`assets/brand/`, plus the plugin's copied banners. Each entry includes its SHA-256,
creation method, parent assets, prompt location when available, and license status.
Markdown guides and OS metadata files are excluded from the asset hash inventory.

It also records every package in `uv.lock`, including locked versions, registry
sources, artifact URLs/hashes, and available installed license metadata. A separate
list records GitHub Actions references. The model registry and known imported
scaffolding and community documentation have their own source records.

This does not reconstruct every contributor's authorship history or prove that all
source code is original. Git history, upstream notices and individual package
licenses remain relevant evidence. Dependency artifact URLs and metadata URLs are
**not** marked checked merely because they appear in the lockfile.

## Brand creation and lineage

The project owner provided creative direction, reviewed iterations, and selected
**Ember** as the primary mascot. Codex wrote prompts and edited assets. OpenAI's
built-in **imagegen** generated the raster artwork. No external stock photographs,
illustrations, icon packs, or uploaded third-party reference images were supplied
or retrieved in this recorded brand workflow. Later edits referenced earlier
AI-generated images. This describes the workflow inputs, not the model's unknown
training sources.

- **Ember:** Inner Glow concept sheet → second-round Inner Glow sheet → standalone
  Ember PNG → Codex-authored SVG redraws → README banners → identical plugin copies.
- **Float:** the same Inner Glow sequence → standalone Float PNG → SVG redraws.
- **Mellow:** Happy Gut 08 → headwear 04 Hood → standalone Hood PNG → copied Mellow
  PNG → SVG redraws. Mellow and Float are retained alternate concepts.
- **Palette:** selected from Ember's plum, coral, gold and cream artwork, with
  contrasting text/surface colors authored for the light and dark themes.

The SVGs are simplified, manually specified Bézier paths authored by Codex with
SVG gradients where applicable. They are not embedded PNGs, automatic traces, or
pixel-identical recreations. “Hand-authored” in earlier asset notes refers to this
path-authoring method, **not a claim of exclusively human-made artwork**.

Saved generation prompts sit beside the later PNGs. Early Happy Gut, Mycelial
Instinct, and first Inner Glow prompts were not saved as repository files; the
conversation provides historical context, but we do not invent missing verbatim
prompt records. Some generation attempts and the earlier branching-logo exploration
were not retained in the repository. This inventory covers the retained files.

The image tool did not expose its underlying model version, seed, training sources,
or reproducibility settings. Those fields are unknown. Audit dates are not inferred
creation timestamps. The vector/HTML assets use system font stacks; no font files
are bundled. Lettering inside generated concept PNGs is generated imagery.

## License boundaries

- **Project:** [LICENSE](LICENSE) declares MIT, copyright 2026 shapeandshare;
  `pyproject.toml` and the plugin package agree. No separate brand-asset license has
  been declared. The JSON records this existing repository default rather than
  inventing a new license or assigning someone else's copyright.
- **AI artwork:** the generation method is disclosed. The inspected
  [OpenAI Terms of Use](https://openai.com/policies/terms-of-use/) discuss rights in
  output and possible non-uniqueness. We have not established which account-specific
  agreement governed these generations. This record does not establish exclusive
  copyright, trademark clearance, or rights in unknown training data.
- **Model artifacts:** Cloudflare's current
  [Clef-Flash card](https://huggingface.co/Cloudflare/clef-flash) and
  [Clef card](https://huggingface.co/Cloudflare/clef) identify Apache-2.0.
  They remain upstream materials, including downloaded `joint_schema_model.py`,
  and are not relicensed by this repository's MIT file. Weights are not bundled.
- **Scaffolding:** `.specify/` and `.opencode/commands/` derive from
  [Spec Kit](https://github.com/github/spec-kit). Local initialization records
  version 1.0.8; the exact upstream commit and per-file changes are not established.
  The checked [current upstream license](https://github.com/github/spec-kit/blob/main/LICENSE)
  is MIT with GitHub, Inc. attribution. That does not independently verify the
  installed release's full notice history.
- **Code of conduct:** [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) identifies its
  [Contributor Covenant 2.1 source](https://www.contributor-covenant.org/version/2/1/code_of_conduct.html)
  and contains project-specific adaptations. Its original attribution remains.
  The historical document license has not been verified. The current upstream
  repository license was inspected but is not assumed to apply retroactively to
  the 2.1 text. This material is not represented as original MIT project prose.
- **Dependencies and CI actions:** retain their own licenses. Installed metadata
  in the JSON is an observation, not independent verification of license scope.
  A package absent from the environment has an explicit unverified status.

Keep third-party license and attribution notices with any redistributed materials.
This inventory does not replace their actual licenses or required notices.

## External URL checks

Checks used web retrieval and content inspection on the recorded date. A failed
fetch is not a finding that a resource does not exist. A successful current page
fetch is not verification of a pinned historical revision. No HTTP status is
invented when the retrieval tool did not expose one.

| Reference | Result |
| --- | --- |
| OpenAI Terms of Use | Retrieved; content ownership/non-uniqueness sections inspected |
| Clef-Flash and Clef current model cards | Retrieved; Apache-2.0 declaration observed |
| Both model cards at the locally pinned commit URLs | Fetch failed; pins verified only in local registry |
| Both current model LICENSE file pages | Fetch failed; local Clef-Flash LICENSE inspected and hashed |
| OpenCode official site | Retrieved; integration reference only |
| MCP official introduction | Retrieved after redirect; protocol reference only |
| Spec Kit project and current LICENSE | Retrieved; MIT / GitHub, Inc. observed |
| Project GitHub repository | Renamed to shapeandshare/ember; verified through the authenticated GitHub API; the old URL redirects |
| Contributor Covenant 2.1 page and FAQ | Retrieved; origin attribution confirmed |
| Contributor Covenant standalone license page | Fetch failed |
| Contributor Covenant current repository LICENSE | Retrieved; historical 2.1 scope remains unresolved |

Exact URLs, redirects, evidence summaries, dates and individual outcomes are in
`external_references` in the JSON. Other external URLs are unverified unless a
check entry explicitly says otherwise. No artwork was downloaded from these pages.

## Maintaining the record

When adding or changing an asset:

1. Save its real prompt, input references, author/tool, and source URL when relevant.
2. Add or update the JSON entry, its parent paths, license evidence and SHA-256.
3. Record edits and copies honestly. Do not label generated work human-made.
4. Recheck an external source before changing its verification date or status.
5. Refresh dependency evidence when `uv.lock` changes; distinguish installed
   versions from locked versions. Do not guess absent license information.
6. Run `python3 scripts/check_provenance.py` to check asset coverage, hashes, parent
   paths, prompt paths, copied banners, and the lockfile fingerprint.

The checker is offline and read-only. It intentionally does not refresh hashes or
mark URLs verified: those actions require reviewing the changed material. A clean
check establishes local consistency, not legal clearance or a fresh URL audit.
