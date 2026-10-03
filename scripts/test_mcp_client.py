"""End-to-end MCP check: initialize, list tools, and call `advise` like an agent would.

Spawns the ember MCP server over stdio against the local server on the default
port, starting it (and loading the model) on first call if it is not already running.

Usage:
    .venv/bin/python -u scripts/test_mcp_client.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mcp import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402


async def main() -> int:
    env = dict(os.environ)
    env.setdefault("EMBER_AUTOSTART", "1")
    env.setdefault("EMBER_START_TIMEOUT", "300")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ember.mcp_server"],
        cwd=str(REPO_ROOT),
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("TOOLS:")
            for tool in tools.tools:
                summary = tool.description.splitlines()[0] if tool.description else ""
                print(f"  - {tool.name}: {summary}")
                print(f"    inputSchema: {json.dumps(tool.input_schema)}")

            arguments = {
                "input": {
                    "state": (
                        "The login endpoint is returning 401 for all users after "
                        "the latest deploy. Nobody can sign in."
                    ),
                    "questions": {
                        "urgent": {"type": "noul", "instructions": "Is this urgent?"},
                        "team": {
                            "type": "choice",
                            "instructions": "Which team should handle this?",
                            "criteria": {
                                "auth": "Authentication/sessions",
                                "frontend": "UI issues",
                            },
                        },
                    },
                }
            }
            print("\nCALL advise ...")
            result = await session.call_tool("advise", arguments)
            print("is_error:", result.is_error)
            if result.structured_content is not None:
                print(
                    "structured_content:",
                    json.dumps(result.structured_content, indent=2),
                )
            for block in result.content:
                text = getattr(block, "text", None)
                if text:
                    print("content:", text)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
