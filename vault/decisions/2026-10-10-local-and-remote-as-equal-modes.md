---
title: "Local, self-hosted, and remote are equal modes"
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/cli
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - ember/commands/agents.py
  - ember/commands/parser.py
  - .specify/memory/constitution.md
---

# Local, self-hosted, and remote are equal modes

Part of [[ember]]. Running the model locally, on a server you host, or on a server someone
else runs are presented and supported as equal choices; none is a fallback.

## Context

Article I ("Local-First by Default", v2.0.0) called local "the core value proposition" and
remote a fallback for users who cannot host the model. The site and README followed: the
hero said "runs on your Mac", and remote setup lived deep in the README. Maintainer direction
was to make remote and self-hosted first class alongside local, in docs and in behavior. See
[[2026-10-06-remote-inference-servers]] for how remote inference arrived.

## Decision

- Constitution v3.2.0 (MINOR): Article I becomes "Local or Remote, Never Silent". Docs and
  onboarding present the three modes side by side, and `ember init` lets a person at a
  terminal choose. The privacy rules are unchanged: an unconfigured or non-interactive
  install is local-only, the default endpoint is loopback, and requests go remote only to one
  explicitly configured endpoint. That is why this is MINOR, not MAJOR.
- `ember init` asks "local or remote?" when stdin and stdout are terminals and neither
  `--local` nor `--server-url` was given; remote then asks for the URL. Without a terminal it
  writes the local entry, as before. `--local` with `--server-url` is an error.
- The site gains a "Run it your way" section and a mode-neutral quick start; the README gains
  a "Ways to run ember" table. "Remote" and "self-hosted" are one client setup (a URL plus an
  optional token) seen from either side; there is no ember-run hosted service.

## Consequences

- A script that ran `ember init` without a terminal behaves exactly as before.
- New docs MUST NOT describe remote as a fallback, or local as the only private option
  without saying where a remote request goes.
- Claude Code is registered with its own CLI, so its remote setup is documented as
  `claude mcp add ... -e EMBER_SERVER_URL=...` rather than through `ember init`.
