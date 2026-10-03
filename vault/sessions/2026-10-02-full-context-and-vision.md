---
title: full context window and vision inputs
type: session-log
tags:
  - type/session-log
  - domain/runtime
  - domain/mcp
  - domain/server
created: 2026-10-02
updated: 2026-10-02
---

# full context window and vision inputs

Part of [[ember]]. A session that raised the default input window to the model's maximum
and wired image/video passthrough into the `advise` tool.

## What happened

- Found the old 16,384-token cap in `ember/config.py` and `ember/runtime.py`, well below the
  pinned backbone's `max_position_embeddings` of 262,144.
- Empirically probed the local `Qwen3VLProcessor`: images accept path/URL/data-URI/base64
  strings, but video frames must be PIL; string frames demand `torchcodec`.
- Verified an image request end-to-end on MPS through `joint_schema_model.systemone`.
- Made `max_length` default to the model's maximum (sentinel `0`), added `ember/media.py`,
  and threaded `images`/`videos`/`media_kwargs` through the MCP and HTTP schemas.
- Updated the agent kit, README, AGENTS.md, and tests.

## Decisions and discoveries written back

- [[2026-10-02-media-refs-are-data-uris-not-host-paths]]

## Follow-ups

- Re-measure the kit's latency numbers with an image input if the recipes gain a vision set.
- Consider a configurable video-frame cap if 64 frames proves too tight.
