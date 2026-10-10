# Contract: MCP `advise` tool (refusal pass-through)

**Feature**: `003-context-window-audit`
**Date**: 2026-10-09
**Scope**: What the agent sees when the server refuses a request. The tool name, input
schema, and success output are unchanged.

## Behavior

- On HTTP 413, the tool raises `ToolError` with exactly
  `ember server error 413: <message>`, where `<message>` is the server's `detail`,
  unchanged (see [http-api.md](./http-api.md)).
- No code change is needed. `_sanitize_error` forwards a 4xx `detail` through `_redact`,
  which rewrites only filesystem paths and traceback markers (`ember/mcp/mcp_server.py`
  L48–71). The message contains no `/` and no `\`, so nothing in it is rewritten.
- Error text from an older remote server passes through as it does today.

## Test

`tests/test_mcp_tool.py` drives the stdio MCP server against a server that answers 413
with a message in the contract format. It asserts two things:
- The `ToolError` text equals `ember server error 413: ` followed by the message,
  character for character.
- The split numbers survive.
