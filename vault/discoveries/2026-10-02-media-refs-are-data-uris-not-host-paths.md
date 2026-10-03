---
title: media refs are data URIs, never host paths or URLs
type: discovery
tags:
  - type/discovery
  - domain/mcp
  - domain/server
  - status/draft
created: 2026-10-02
updated: 2026-10-02
code-refs:
  - ember/media.py
  - ember/runtime.py
  - ember/mcp_server.py
---

# media refs are data URIs, never host paths or URLs

Part of [[ember]]. The `advise` tool takes images and video frames, but the wire format
deliberately accepts only inline base64 — not local paths or remote URLs — so an
agent-supplied ref can never make the warm model server read a host file or fetch a URL.

## What was tested

- The pinned `Qwen3VLProcessor` was called directly with images as PIL, a file path, an
  `http:` URL, a `data:` URI, and bare base64: all decode, because the processor's loader
  accepts strings.
- The same processor rejects string video frames (`torchcodec` is not installed); only a
  list of PIL frames works.
- A full image request through `joint_schema_model.systemone` on MPS returned a calibrated
  answer (a red swatch classified `red` at P=0.98, 300 input tokens).

## Finding

- Cloudflare's hosted Clef schema accepts `data:image/...;base64,...` strings or
  `{content_type, base64}` objects and rejects remote URLs.
- The open-source `systemone` has no wire convention at all — it wants PIL objects — so the
  decode layer is ember's to own.
- Accepting local paths would turn the server into an arbitrary file-read oracle for a
  prompt-injected agent; accepting URLs adds SSRF surface. Both are avoidable because the
  primary path (agents base64-encode screenshots) needs neither.

## Relevance

- `ember/media.py` decodes `data:` URIs and `{content_type, base64}` objects and raises
  `ValueError` for anything else, which the HTTP server reports as 422. The png/jpeg/webp
  allowlist is enforced on both forms, and image count and video-frame totals are capped to
  bound MPS memory.
- Video frames are decoded to PIL before Clef's processor sees them.
- Decoding runs only in the model-server process (`Engine.advise`); `mcp_server` forwards
  strings so it stays free of torch and PIL.

## References

- `ember/media.py` (decode + trust boundary)
- `ember/runtime.py` (`Engine.advise` decodes; `model_max_length`)
- Cloudflare's `clef-flash` input schema (`images` anyOf data-URL / base64 object)
