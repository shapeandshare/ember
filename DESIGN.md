# Design System

This document is the source of truth for how `ember` looks, is documented,
and is structured. It governs documentation conventions, visual language,
architectural diagram style, code and prose standards, and contributor workflow.
It is not a user guide.

**Authority.** `.specify/memory/constitution.md` is supreme. Where this
document and the constitution conflict, the constitution wins and this file must be
updated to match.

---

## 1. Project Identity

`ember` (package: `ember`) is a local, private decision oracle for
coding agents. It runs Cloudflare's Clef decision model on Apple Silicon via MPS
and exposes it as a single MCP tool. It produces calibrated probabilities, not
prose. There is no cloud path, no text generation, and no opinion.

**Brand voice**: precise, minimal, honest. Numbers over adjectives. The tool
answers questions; it does not editorialize. Documentation follows the same
register: declarative for descriptions, imperative for instructions, no hype.

**What it is not**: a chat model, a reasoning engine, a cloud service, or a
general-purpose assistant. Every documentation choice should reinforce the
boundary between "typed decision output" and "text generation."

---

## 2. Mascot and Color Palette

**Ember is the primary mascot** and the product's namesake: a curled plum
creature embracing a warm glowing tummy. Use `assets/brand/svg/ember-light.svg`
on light surfaces and `ember-dark.svg` on dark surfaces. Both have transparent
backgrounds; `ember-auto.svg` follows system theme. Detailed illustration:
`assets/brand/mascots/ember-v1.png`. Mellow and Float are retained alternate
concepts, not the primary identity.

The brand asset guide is `assets/brand/README.md`; reusable semantic CSS tokens live
in `assets/brand/tokens.css`. README banners use `assets/brand/hero-{light,dark}.svg`.

| Color | Hex | Role |
| --- | --- | --- |
| Plum | `#603050` | Primary identity; links and accents on cream |
| Coral | `#D65E64` | Warm decorative accent |
| Gold | `#FFC24D` | Inner glow; links and accents on dark surfaces |
| Cream | `#FFF8EB` | Light surface; text on dark surfaces |
| Ink | `#201922` | Dark surface; text on light surfaces |

Light secondary text is `#715568`; dark secondary text is `#D8BFCB`.
Decorative mascot gradients include peach, orange, and plum shades derived from
the artwork. Do not use coral or gold as small text on cream. The historical
four-color Steel/Amber/Sage palette is superseded by Ember's palette.

Statuses must have explicit labels or icons; never rely on color alone.
GitHub Markdown keeps the reader's native text colors; themed artwork carries the
palette there. Rendered web documentation can consume the semantic CSS tokens.

---

## 3. Typography

Documentation renders in the reader's system font. No custom web fonts, no
`@font-face`, no CDN requests.

| Context          | Stack                                                                 |
|------------------|-----------------------------------------------------------------------|
| Body / headings  | `system-ui, -apple-system, sans-serif`                                |
| Inline code      | `ui-monospace, SF Mono, Menlo, Cascadia Code, Consolas, monospace`    |
| Code blocks      | same monospace stack                                                  |
| Diagram labels   | `system-ui, -apple-system, sans-serif`                                |

No serif fonts anywhere. No decorative fonts. The monospace stack is used for
all code, all command output, all tool call payloads, and all file paths.

---

## 4. Diagrams

### Format

ASCII box-and-arrow diagrams are the default for inline documentation. They are
diffable and render everywhere. Use them for architecture, call paths, and data
flow. The README's architecture call path is the exception: it is a hand-authored
SVG plate (`assets/diagrams/call-path-light.svg` and `call-path-dark.svg`),
referenced with `<picture>` so the website renders it as a figure.

```
component-a ──────────────────► component-b
                                      │
                                      ▼
                               component-c
```

If a standalone visual asset is needed (hero banner, explainer plate), use
hand-authored SVG. SVG assets live in `assets/`. They must use the Ember
palette, the system-ui font stack, and a `viewBox` attribute on the root element.
No hardcoded `width`/`height` in pixels on the root `<svg>`.

**Mermaid is not used.** Not in the README, not in docs, not in any markdown
file. The constitution does not prohibit it explicitly, but the project's
documentation style is ASCII-first; Mermaid diagrams are auto-generated and
visually inconsistent with that register.

### ASCII diagram conventions

- Use `─` (U+2500) for horizontal lines, `│` (U+2502) for vertical.
- Use `►` or `▼` for directed arrows.
- Use `┌ ┐ └ ┘` for box corners when boxing a component.
- Label boxes with the module or component name, not a description.
- Keep diagrams narrow enough to read at 80 columns without horizontal scroll.

### SVG conventions

1. Font stack: `system-ui, -apple-system, sans-serif` for labels; monospace
   stack for code or path text.
2. Colors: palette tokens only.
3. No SMIL `<animate>` tags. Use CSS `@keyframes` inside a `<style>` block.
4. `viewBox` is required on every root `<svg>`.
5. Alt text is required on every `<img>` referencing an SVG.
6. Dark/light variants use `<picture>` with
   `<source media="(prefers-color-scheme: dark)">`.

---

## 5. README Structure

The README follows a fixed section order. Do not reorder sections or add new
top-level sections without updating this document.

```
1.  Title / one-line description
2.  Badges row
3.  Why it's built this way (architecture rationale + call-path SVG plate)
4.  Verified (benchmark table: model load time, warm inference, tool call result)
5.  Layout (directory tree)
6.  Install
7.  CLI (command reference)
8.  Agent onboarding (channels table + per-agent notes)
9.  Development setup
10. Run (server lifecycle)
11. Make targets (table)
12. Usage (example tool call + JSON response)
13. Tests
14. Caveats
15. Troubleshooting
16. License
```

Every `##` section heading uses plain English, no emoji prefix. The README is a
technical reference, not a marketing page.

### Section conventions

- **Why it's built this way** explains the architectural split (MCP server /
  HTTP server / model) and includes the call-path SVG plate. This section
  answers "why not just point opencode at the model directly."
- **Verified** contains a pipe table with measured numbers from a real run on
  the reference hardware (M4 Max / 128 GB). Numbers must come from actual
  measurement, not estimates. Re-measure when the pinned model revision changes.
- **Layout** is a directory tree code block, not prose.
- **Make targets** is a pipe table with two columns: target and description.
- **Caveats** covers known limitations that affect correctness or behavior.
  Not a troubleshooting section.
- **Troubleshooting** covers failure modes with a cause and a fix.

---

## 6. Badges

Three badges only, in this order:

| Badge          | Color     | Links to              |
|----------------|-----------|-----------------------|
| Python version | `#3776ab` | python.org/downloads  |
| License        | `#4a7fa5` | LICENSE file          |
| CI status      | provider  | CI workflow run       |

No vanity badges: no download counts, no star counts, no "made with" badges, no
code style badges. The badge row communicates the minimum a contributor needs to
know before reading further.

Use `style=for-the-badge` on all shields.io badges. Separate badges with
`&nbsp;`.

---

## 7. Callout Conventions

Use blockquote callouts for emphasis. Three types:

```markdown
> **Note:** Informational context the reader might not expect.

> **Warning:** Something that can cause incorrect behavior or data loss.

> **Tip:** A non-obvious shortcut or better approach.
```

Rules:

- One callout per section maximum. Overuse dilutes impact.
- Use `Warning` for anything that can cause silent failure, data loss, or
  security issues.
- Use `Note` for cross-references and non-obvious constraints.
- Use `Tip` for shortcuts and better approaches.
- Never use callouts for routine information.
- Do not use HTML `<details>` blocks except for long reference tables that would
  break the flow of a section. When used, the `<summary>` must be a plain string,
  not a heading element.

---

## 8. Table Conventions

All tables use pipe-table Markdown syntax. Every table has a header row. Align
columns with spaces for readability in source.

```markdown
| Column A     | Column B     | Column C     |
|--------------|--------------|--------------|
| value        | value        | value        |
```

- Keep tables under 8 rows in the main README. Link to a reference document for
  longer lists.
- Status columns (pass/fail, yes/no) use `✅` and `❌` with `:---:` alignment.
- The first column of a reference table is often monospace (command names, file
  paths, environment variables). Wrap those values in backticks.
- Do not use HTML `<table>` in the README except for multi-column feature grids
  where pipe tables cannot express the layout.

---

## 9. Code Block Conventions

Every fenced code block carries a language tag. No unnamed blocks.

| Content                        | Tag      |
|--------------------------------|----------|
| Shell commands                 | `bash`   |
| Python source                  | `python` |
| JSON payloads / responses      | `json`   |
| Directory trees                | `text`   |
| Plain output / log lines       | `text`   |
| TOML configuration             | `toml`   |

Shell commands in `bash` blocks use the bare command, no `$` prompt prefix,
unless showing interactive output alongside the command. When showing a command
and its output together, use `text`.

---

## 10. Documentation Language

- **Imperative mood** for instructions: "Run `make bootstrap`", "Set
  `EMBER_PORT`", "Restart opencode."
- **Declarative** for descriptions: "The MCP server starts the HTTP server on
  first use", "Weights are pinned to a Hugging Face commit SHA."
- **Plain English.** Avoid: "just", "simply", "easily", "leverage", "utilize",
  "in order to", "moving forward", "robust", "streamline", "facilitate".
- No exclamation marks.
- No em dashes or en dashes. Use commas, periods, or line breaks instead.
- Contractions are fine: "don't", "it's", "you'll".
- Vary sentence length. Short sentences for instructions. Longer sentences for
  explanations, when the relationship between ideas needs to be explicit.
- Never start consecutive sentences with the same word.

---

## 11. Architecture Diagram Style

The canonical call-path diagram is the SVG plate
(`assets/diagrams/call-path-light.svg` and `call-path-dark.svg`). The ASCII below
is its text fallback — keep the two in step:

```
agent ──tools/call advise──► ember-mcp (stdio, mcp_server.py)
                               │  initialize.instructions + ember://guide
                               ▼  lazy autostart of a PID-tracked child
                     HTTP POST /v1/systemone (server.py)
                               │
                               ▼
                     Engine.advise (runtime.py)
                               │
                               ▼
                     Clef model on MPS (fp16)
```

Rules for architecture diagrams:

- Show the actual module names, not abstract layer names.
- Show the transport (stdio, HTTP POST, function call) on the arrow.
- Show the port or path when it is a fixed contract.
- Keep the diagram narrow enough to read at 80 columns.
- Do not show internal implementation details (class hierarchies, private
  methods). Show the call path a contributor needs to follow a request.

---

## 12. Commit Conventions

Conventional commits. Format:

```
<type>: <subject>
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`.

Subject rules:

- Imperative mood: "add", "fix", "remove", not "added", "fixes", "removed".
- Lowercase after the type prefix.
- No period at the end.
- 72 characters maximum.
- Plain English. No marketing language.

Examples:

```
feat: add score question type to advise tool
fix: prevent double autostart when port is already bound
docs: update verified table for clef-flash 17f0b0a
chore: pin torchvision to 0.29 series
refactor: extract port-probe logic into process.py
test: add mcp autostart test with random port
```

Body and footer are optional. When present, the body explains why, not what.
The what is in the subject and the diff.

---

## 13. Pull Request Conventions

- One logical change per PR. A PR that fixes a bug and adds a feature is two PRs.
- The description references the spec (`.specify/`) or the issue it addresses.
- Every PR that changes the runtime, servers, CLI, or agent kit must include
  passing `make test` output or a CI link.
- Agent-kit changes (anything under `ember/agent_kit/`) are public-API
  changes. The PR description must note what downstream agents will see differently
  and confirm that `instructions.md` stays within 2048 bytes.
- Do not merge with failing CI.

---

## 14. Makefile Conventions

The root `Makefile` is a thin orchestrator. It defines variables, declares
`.PHONY` targets, and delegates to the `ember` CLI for server lifecycle
operations. It does not contain business logic.

### Target documentation

Every public target carries a `## ` comment on the same line. The `help` target
harvests these with an `awk` one-liner:

```makefile
help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / \
	    {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
```

This pattern is shared across sibling repos. Keep it intact.

### Variable conventions

Environment variable overrides use `?=` so callers can override from the shell.
Variables that must be exported to child processes use `export`. The three
server-configuration variables (`EMBER_HOST`, `EMBER_PORT`,
`EMBER_DEVICE`) are always exported.

### Target groups

Targets are grouped by concern with a comment header:

```
# environment      — setup, sync, download, init, bootstrap
# server lifecycle — serve, start, stop, restart, status, logs, mcp
# quality          — test, test-fast, test-strict, mcp-check, smoke, compile, check, ci
# maintenance      — clean, clean-model
```

If the project grows to warrant splitting, the pattern from sibling repos is a
`shared/` directory of `.mk` domain files (`shared/python.mk`,
`shared/testing.mk`, `shared/server.mk`, `shared/release.mk`) included by the
root Makefile. The root stays a thin orchestrator; domain logic moves to the
include files. The `## ` help-comment convention applies to all included files.

---

## 15. Tooling Stack

All tool configuration lives in `pyproject.toml`. No separate `ruff.toml`,
`mypy.ini`, `.bandit`, or `.coveragerc`. One file per concern.

| Tool         | Role                                      | Config section              |
|--------------|-------------------------------------------|-----------------------------|
| `uv`         | Dependency management, venv, lock file    | `pyproject.toml` + `uv.lock`|
| `ruff`       | Format and lint                           | `[tool.ruff]`               |
| `mypy`       | Static type checking (strict mode)        | `[tool.mypy]`               |
| `bandit`     | Security linting                          | `[tool.bandit]`             |
| `pytest`     | Test runner                               | `[tool.pytest.ini_options]` |
| `pytest-cov` | Coverage measurement and floor ratchet    | `[tool.coverage]`           |
| `commitizen` | Version bumps and changelog generation    | `[tool.commitizen]`         |
| `hatchling`  | Build backend                             | `[build-system]`            |

### Type checking

`mypy` runs in strict mode. No `# type: ignore` comments without an inline
explanation. No `Any` in public interfaces. The MCP server and HTTP server
modules are fully typed; the model runtime module is typed to the extent the
upstream `joint_schema_model.py` allows.

### Linting

`ruff` handles both formatting and linting. It replaces `black`, `isort`, and
`flake8`. The format is the canonical style; do not run `black` separately.

### Security

`bandit` runs on the `ember/` package. The MCP server and HTTP server
are the primary attack surface: they accept external input and pass it to the
model. Any `bandit` finding in those modules is a blocker.

### Coverage

A coverage floor is enforced via `pytest-cov`. The floor ratchets upward; it
never moves down. New code without tests fails the gate.

---

## 16. Configuration Location

All persistent configuration lives in `~/Library/Application Support/ember`
on macOS (resolved by `ember/paths.py`). The server binds to
`127.0.0.1:8765` by default. Both are overridable via environment variables
(`EMBER_HOST`, `EMBER_PORT`).

Per-machine generated files (`opencode.json`, `.opencode/plugins/ember.js`)
embed absolute paths and are gitignored. Regenerate them with `make init` or
`make opencode` after cloning. Never commit them.

`uv.lock` is committed. CI installs with `uv sync --locked`. Widening a
dependency range requires green model-backed tests.

---

## 17. Agent Kit Conventions

`ember/agent_kit/` is the single source of truth for everything a
consumer's agent reads. The three delivery channels are:

| File                          | Delivered as                    | Constraint                  |
|-------------------------------|---------------------------------|-----------------------------|
| `instructions.md`             | MCP `initialize.instructions`   | Must stay within 2048 bytes |
| `ember-advise/SKILL.md`       | MCP resource `ember://guide`; skill via `ember agents install` | Skill name must match directory |
| `AGENTS.snippet.md`           | `ember agents show snippet`     | No constraint on size       |

Rules:

- The skill name must stay `ember-advise` and match its directory name.
- Thresholds and "Observed" numbers in the kit must come from real model output.
  Re-measure them when the pinned model revision changes or when a recipe schema
  changes. Questions are scored jointly; changing one question changes all scores.
- The tool name, input schema, and kit text are public API. Change them together
  with the README and the tests in `tests/test_agent_kit.py`,
  `tests/test_mcp_tool.py`, and `tests/test_cli.py`.
- `instructions.md` byte count must be verified after every edit. The check
  belongs in `tests/test_agent_kit.py`.

---

## 18. Testing Conventions

Tests live in `tests/`. The suite has two tiers, separated by the `model` marker:

| Tier          | Marker          | What runs                                      | Speed   |
|---------------|-----------------|------------------------------------------------|---------|
| Unit          | (no marker)     | Schema validation, config, CLI, MCP protocol   | ~11 s   |
| Model-backed  | `@pytest.mark.model` | Full inference, HTTP server, MCP end-to-end | ~35 s   |

`make check` runs the unit tier only. `make test` runs both. `make test-strict`
runs both and fails (not skips) when weights are missing.

### Safety rules

Tests must not interfere with a host running other opencode instances or other
servers:

- Bind a random free port. Never bind `8765`.
- Start only processes the test itself launched, tracked by PID.
- Stop only those processes. Never kill by port or by pattern.
- Never invoke the opencode CLI.
- Never mutate global opencode configuration.

These rules come from Article IV of the constitution. They are not optional.

---

## 19. Maintenance Checklist

When editing any documentation file:

- [ ] Colors match the four-token palette (§2)
- [ ] Diagrams are ASCII or hand-authored SVG, not Mermaid (§4)
- [ ] README section order preserved (§5)
- [ ] Badge set is exactly three badges (§6)
- [ ] At most one callout per section (§7)
- [ ] All tables have a header row and aligned columns (§8)
- [ ] All code blocks carry a language tag (§9)
- [ ] No em dashes, no exclamation marks, no banned phrases (§10)
- [ ] Verified table numbers come from a real run (§5)
- [ ] Agent kit byte count checked if `instructions.md` was touched (§17)
- [ ] `make check` passes

---

## Changelog

| Date       | Change                                                        |
|------------|---------------------------------------------------------------|
| 2026-10-02 | Initial design system: palette, typography, diagram style, README structure, badges, callouts, tables, code blocks, language, architecture diagrams, commits, PRs, Makefile, tooling, config, agent kit, testing, maintenance checklist |
| 2026-10-02 | Product renamed to `ember` to match the mascot; "gut feeling" stays as flavor text |

## Material provenance

[PROVENANCE.md](PROVENANCE.md) explains material origins and license boundaries.
[provenance.json](provenance.json) records brand asset hashes and lineage, model
sources, dependency evidence, and dated external URL checks. Update it when
changing brand materials; run `python3 scripts/check_provenance.py`.

Related root documents: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) summarizes code
dependency licenses, [COMPATIBILITY.md](COMPATIBILITY.md) records tested models and
versions, and [RESPONSIBLE_USE.md](RESPONSIBLE_USE.md) states the intended and excluded
uses.
