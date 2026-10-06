# Support

## Getting help

- **Bugs and feature requests**: open an issue on [GitHub Issues](https://github.com/shapeandshare/ember/issues).
- **Questions and usage help**: start a thread in [GitHub Discussions](https://github.com/shapeandshare/ember/discussions).

Please use the right channel. Questions filed as issues will be redirected to Discussions.

## Before you ask

Most problems have a quick answer. Work through this checklist first:

1. **Run `ember doctor`** — it reports platform readiness, model availability, and server
   status in one shot. Include its output in any bug report.
2. **Run `ember status`** — confirms whether the warm server is running and responding.
3. **Check `ember logs`** — the server log often contains the exact error.
4. **Read the Troubleshooting section of README.md** — common setup and runtime issues are
   documented there.
5. **Search existing issues and discussions** — your question may already have an answer.

## Filing a good bug report

A useful bug report includes:

- The full output of `make doctor`
- The complete error message or stack trace
- The exact `make` target or `ember` / `gut` CLI command that triggered the issue
- Your macOS version and chip (e.g., M2 Pro)
- Whether the issue is reproducible with `EMBER_DEVICE=cpu`

Without `make doctor` output, diagnosing environment-specific issues is slow. Please include
it even if the problem seems unrelated to the environment.

## AI agent filing etiquette

Agents filing issues must:

- Identify which agent system generated the report (e.g., "Filed by opencode using the
  ember MCP server").
- Confirm that `make doctor` output was checked and include it in the report.
- Confirm the issue is not a pre-existing known caveat documented in README.md Troubleshooting.

Issues filed by agents that skip these steps will be closed and the operator asked to re-file
with the required information.

## What not to file

Some things are outside the scope of this project's support:

- **Upstream Clef model behavior**: if the model's probability outputs seem wrong for a given
  input, that's a model-level concern. Report it to Cloudflare or the Hugging Face repository.
- **Third-party tool configuration**: issues with your opencode setup, Claude Code MCP
  configuration, or other agent tooling that aren't specific to ember.
- **Questions already answered in README.md Troubleshooting**: check there first.

For security vulnerabilities, see [SECURITY.md](SECURITY.md). Do not open a public issue.
