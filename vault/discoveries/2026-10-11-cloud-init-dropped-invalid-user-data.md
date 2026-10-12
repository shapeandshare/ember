---
code-refs:
  - deployment/aws/instance/cloud-init.yaml
  - deployment/aws/ember_aws/user_data.py
  - tests/test_aws_instance_scripts.py
created: 2026-10-11
tags:
  - type/discovery
  - domain/server
  - domain/tooling
  - status/draft
title: Cloud-init silently dropped the instance user data (unindented heredocs)
type: discovery
updated: 2026-10-11
---
# Cloud-init silently dropped the instance user data (unindented heredocs)

Part of [[ember]]. On the first live `make aws-up`, the instance booted, installed nothing, joined no tailnet, and served nothing. The delivered user data was invalid YAML, so cloud-init rejected the whole blob and ran an empty cloud-config — with no error reaching the deploy command.

## What was tested

- `aws ec2 get-console-output` showed cloud-init rejecting the blob: `util.py[WARNING]: Failed loading yaml blob. Invalid format at line 67 column 1: set -euo pipefail ... could not find expected ':'` followed by `cloud_config.py[WARNING]: Failed at merging in cloud config part from part-001: empty cloud config`.
- `aws ec2 describe-instance-attribute --attribute userData` (base64-decoded) showed the render with every placeholder substituted, but each heredoc body (`tailscale-join.sh`, `converge.sh`, the systemd units) at column 0.
- `yaml.safe_load(rendered)` raised; `yaml.load(UserData.template_body(rendered))` did not.

## Finding

`deployment/aws/instance/cloud-init.yaml` writes the scripts and units through `cat > … << 'SCRIPT_EOF'` heredocs inside `- |` block scalars. Every heredoc body line sat at column 0. YAML ends a block scalar at the first line less indented than its content, so each `- |` scalar ended at the first `#!…`/`[Unit]` line and the rest was reparsed as YAML — invalid.

`UserData.template_body()` then indents the render by 10 spaces and embeds it under `Fn::Base64: |`; the outer scalar survives (its own content is indented ≥10), so CloudFormation accepted the template and delivered the broken blob to the instance, where cloud-init discarded it.

The guard that should have caught this — `test_template_body_parses_as_yaml` — parsed only the CFN embedding, where the entire render is one inert scalar: it can never fail on YAML *inside* the user data. The suite now parses the rendered user data as cloud-config and asserts `runcmd` survives.

## Relevance

- Fix: indent every heredoc body by 4 spaces; YAML strips the common indent, so the scripts reach the shell unchanged with their terminators back at column 0. Verified with `bash -n` on both extracted scripts and the nested `PYEOF` heredoc.
- Lesson for the next person: a cloud-config template must be validated by parsing the **render**, not the CFN embedding. The delivery path (block-scalar wrapping, base64, cloud-init) can hide any YAML error in the inner document.
- The same class of silent failure is possible for any helper script embedded as a heredoc; keep every body line indented inside its block scalar.

## References

- `deployment/aws/instance/cloud-init.yaml` — the five heredoc regions
- `deployment/aws/ember_aws/user_data.py` — `render()`, `template_body()`
- `tests/test_aws_instance_scripts.py` — `test_rendered_user_data_parses_as_cloud_config`
- commit `066d089` — the fix
