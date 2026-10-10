---
title: ember vault
type: moc
tags:
  - type/moc
  - domain/governance
created: 2026-10-02
updated: 2026-10-10
---

# ember vault

The hub of the ember knowledge vault: the governed memory of this project's own
development (constitution Article IX). It holds the agent audit trail of
decisions, discoveries, and session logs, and links out to the documents it must
never duplicate.

## Contents

### Decisions

Session-level decisions with their context and consequences.

- [[2026-10-02-rename-the-product-to-ember]]
- [[2026-10-03-adopt-peer-python-conventions]]
- [[2026-10-02-publish-as-gut-and-opencode-ember-advise]]
- [[2026-10-02-adopt-a-governed-project-vault]]
- [[2026-10-02-expose-prometheus-metrics-on-the-server]]
- [[2026-10-03-freeze-benchmark-labels-before-runs]]
- [[2026-10-03-measure-ember-through-the-agent]]
- [[2026-10-03-harden-github-before-going-public]]
- [[2026-10-03-publish-a-pages-site]]
- [[2026-10-04-implicit-namespace-packages]]
- [[2026-10-04-ownership-policy-reinstatement]]
- [[2026-10-04-extract-mcp-types-to-own-module]]
- [[2026-10-04-restructure-into-sub-packages]]
- [[2026-10-04-move-eval-harness-to-evals-eval]]
- [[2026-10-04-constitutional-articles-xi-xv]]
- [[2026-10-04-version-components-separately]]
- [[2026-10-05-decision-models-are-the-category]]
- [[2026-10-06-remote-inference-servers]]
- [[2026-10-07-kilo-code-first-class-harness]]
- [[2026-10-07-bootstrap-clients-against-hosted-endpoints]]
- [[2026-10-07-anaconda-models-as-preferred-provider]]
- [[2026-10-08-outerbounds-hosted-s3-model-location]]
- [[2026-10-08-article-v-redefined-model-loading]]
- [[2026-10-08-optional-s3-credentials-iam-role]]
- [[2026-10-08-simplify-remove-anaconda-s3-registry-entries]]
- [[2026-10-08-outerbounds-deployment-and-cuda-support]]
- [[2026-10-08-doctor-reports-registration-from-config-files]]
- [[2026-10-09-publish-releases-to-pypi-and-the-mcp-registry]]
- [[2026-10-10-remove-t004-non-loopback-auth-check]]
- [[2026-10-10-per-model-request-caps]]

### Discoveries

Non-obvious constraints, gaps, and conflicts that cost discovery time.

- [[2026-10-02-ember-names-are-taken-on-pypi-and-npm]]
- [[2026-10-02-opencode-merges-the-dot-opencode-config]]
- [[2026-10-02-media-refs-are-data-uris-not-host-paths]]
- [[2026-10-03-self-hosted-vms-cannot-hold-the-model]]
- [[2026-10-05-release-automation-constraints]]
- [[2026-10-06-constitution-consistency-audit]]
- [[2026-10-08-config-show-ignored-env-overrides]]
- [[2026-10-08-ember-init-leaked-the-vault-server]]
- [[2026-10-08-harnesses-gate-project-mcp-registrations]]
- [[2026-10-08-release-resume-tagged-main-head]]
- [[2026-10-09-docker-desktop-drops-deletion-events]]
- [[2026-10-09-pypi-json-api-hides-empty-projects]]
- [[2026-10-09-request-size-checks-miss-what-the-model-sees]]
- [[2026-10-10-fast-bakery-strips-ember-advise-from-deploy-requirements]]
- [[2026-10-10-probe-items-cannot-resolve-the-tolerance]]
- [[2026-10-10-memory-checks-bound-each-models-cap]]
- [[2026-10-10-remote-health-probe-sent-no-auth-header]]

### Sessions

- [[2026-10-04-sonarcloud-scanning]] — add SonarCloud scanning to CI
- [[2026-10-08-codex-review-and-s3-rename]] — Codex init review fixes; neutral S3 setting names
- [[2026-10-08-client-registration-hygiene]] — `ember init` registers only ember; doctor reports per-harness registration
- [[2026-10-09-context-window-audit-implementation]] — full-request counting, refusals, limit reporting, and the long-context probe
- [[2026-10-10-pilot-gate-and-per-model-caps]] — the pilot's sizing gate, memory checks, per-model fallback caps, and a larger benchmark

Append-only session logs, never pruned.

- [[2026-10-02-ember-rename-and-vault-bootstrap]]
- [[2026-10-02-full-context-and-vision]]
- [[2026-10-02-prometheus-metrics]]
- [[2026-10-03-advise-eval-harness]]
- [[2026-10-03-eval-benchmark-harness]]
- [[2026-10-05-per-component-releases]]

## Reference

- [[tags|Tag vocabulary]]: the controlled vocabulary every note draws from
- Templates: `vault/_meta/templates/`

## External anchors (outside the vault)

- Constitution: `.specify/memory/constitution.md`
- Agent operating guide: `AGENTS.md`
- User documentation: `README.md`
- Design system: `DESIGN.md`
- Provenance: `PROVENANCE.md` and `provenance.json`
- What consumers' agents read: `ember/agent_kit/`
