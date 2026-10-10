## v0.10.1 (2026-10-10)

### Fix

- **ember**: send the configured auth header on the remote health probe (#102)

## v0.10.0 (2026-10-10)

### Feat

- **ember**: give each registered model its own memory-checked fallback request cap (#96)

## v0.9.1 (2026-10-10)

### Fix

- **ember**: remove T-004's non-loopback-without-auth startup check (#99)

## v0.9.0 (2026-10-10)

### Feat

- **ember**: count requests in full, refuse oversized ones, and measure per-model caps (#94)

### Fix

- **ember**: install ember-advise itself in the Outerbounds deploy image (#97)

## v0.8.1 (2026-10-09)

### Fix

- **ember**: STRIDE security mitigations — 11 threats resolved across all layers (#92)

## v0.8.0 (2026-10-09)

### BREAKING CHANGE

- the distribution is now ember-advise. Existing tool
installs must run `uv tool uninstall gut` before installing it.

### Feat

- **ember**: publish releases to PyPI as ember-advise and the MCP Registry (#86)

## v0.7.0 (2026-10-09)

### Feat

- **ember**: add --version / -V flag to CLI (#83)

## v0.6.0 (2026-10-08)

The release run for #76 timed out before tagging, and the resumed run tagged `main` after
#79 merged, so v0.6.0 also ships #78 and #79.

### Feat

- **ember**: Outerbounds hosted deployment with CUDA support and S3 model loading (#76)
- **ember**: fix Outerbounds hosted deployment for real-world use (#78)
- **ember**: Codex CLI registration, per-harness doctor report, and safe ember init (#79)

## v0.5.0 (2026-10-07)

### Feat

- **ember**: add Kilo Code support and remote endpoint bootstrap (#74)

## v0.4.0 (2026-10-06)

### Feat

- **ember**: support remote inference servers (#70)

### Fix

- **site**: open the docs at the overview instead of a contents page (#68)

## v0.3.2 (2026-10-05)

### Fix

- **ember**: clear the SonarCloud findings and validate opencode config paths (#64)

## v0.3.1 (2026-10-05)

### Fix

- **ember**: audit server stops in the server log (#60)
- **ember**: bound the advise queue and cap per-request tokens (#59)
- **ember**: enforce trust boundaries — loopback URL, media kwargs allowlist, EMBER_MCP validation (#58)
- **ember**: verify model files before import and load (#57)
- **plugin**: respect EMBER_AUTOSTART from the environment (#48)
- **plugin**: extract release notes with prefix match (#44)

## v0.3.0 (2026-10-05)

### Feat

- test both release paths end-to-end (#40)
- **plugin**: add clef and advise to npm keywords (#37)
- **plugin**: add version history link to README (#33)
- **ember**: export __all__ from package root (#32)

## v0.2.0 (2026-10-04)

### Feat

- constitutional compliance and full codebase restructure (#23)
- add a light/dark theme toggle (#22)
- make the landing links say what they lead to (#17)
- add the GitHub Pages site (#15)
- add the eval harness and harden GitHub before going public (#11)
- add a governed project vault (#5)
- rebrand the opencode plugin package as opencode-gut-feeling

### Fix

- lift the code panel in dark mode (#21)
- add an Open Graph image so link previews render (#20)
- rebuild the site when a published document changes (#19)

### Refactor

- rename the opencode plugin package to opencode-ember-advise
- rename the package, CLI, and MCP server to ember
- rename the product to gut-feeling
