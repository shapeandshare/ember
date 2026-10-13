---
title: "A deployment update deleted the tailnet device it never replaced"
type: discovery
tags:
  - type/discovery
  - domain/server
  - domain/tooling
  - status/draft
created: "2026-10-13"
updated: "2026-10-13"
code-refs:
  - deployment/aws/ember_aws/stack.py
  - deployment/aws/ember_aws/lifecycle_update.py
  - deployment/aws/instance/tailscale-join.sh
---

# A deployment update deleted the tailnet device it never replaced

Part of [[ember]]. Upgrading the AWS deployment to v0.15.0 took four real-API
fixes and ended in a stranded node: the update path asked a change-set preview
"does this replace the instance?", took "yes" as licence to delete the tailnet
device and mint a fresh join key — and CloudFormation then updated in place.
The instance kept its Tailscale state ("already logged in, skipping join"), so
the deleted device was never re-registered: the server ran, unreachable.

## What was tested

An `make aws-up EMBER_VERSION=0.15.0` against the live stack (g5.2xlarge →
g6e.xlarge), read through CloudFormation events, `get-console-output`, SSM
parameters, and the tailnet device list; then recovery by `aws-down` +
`aws-up`, and the CUDA legs re-run.

## Finding

Four failures, in the order they surfaced:

1. Update change sets carried no template — `Either Template URL or Template
   Body must be specified`.
2. The callers never supplied `_template_body`; the first fix sent a
   zero-length body (min length 1).
3. Change sets then demanded the unchanged parameters' values
   (`DeploymentName, VpcId, ImageId, CacheBucket, SubnetId`) — now merged from
   `stack_parameters.read` as the base.
4. A no-op change set is **created in the FAILED state**; the waiter's message
   does not carry the reason, so emptiness detection must read
   `describe_change_set`'s `StatusReason` ("didn't contain changes") — fixed,
   with best-effort cleanup of the failed change set.

And the stranded-node defect: `update_has_replacement` trusts the change-set
preview's `Replacement` flag; for this update the preview said replacement
while execution was in place — devices were deleted pre-emptively, the boot
script skipped the join (local state `Running`), and the node vanished from
the tailnet while the server stayed up. Recovery: `aws-down` + `aws-up`
(fresh device + join key).

## Relevance

Do not delete tailnet devices before the update actually replaces the
instance: verify the physical instance id after `stack.wait("update")`, or
reconcile (re-mint the key / re-register) when a previewed replacement does
not replace. Tracked as T042 in specs/007. The deployment now runs 0.15.0
with the CUDA legs re-run clean (tag_assignment 65/65 at 80.5%,
note_placement 30/30 at 56.7%, zero refusals).

## References

- `deployment/aws/ember_aws/stack.py`, `deployment/aws/ember_aws/lifecycle_update.py`
- `deployment/aws/instance/tailscale-join.sh`
- [[2026-10-12-cuda-deployment-request-cap-drift]]
- PR #127 (the fixes)
