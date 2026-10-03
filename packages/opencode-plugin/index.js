// Register the local Clef decision-model MCP server with opencode.
//
// Register-only: the server stays lazy and is started on first tool call.
// Resolves `clef-mcp` from CLEF_MCP, the uv-tool bin dir, or Homebrew, and
// passes an explicit PATH because opencode launched from a GUI can have a
// stripped environment.
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function resolveClefMcp() {
  const candidates = [
    process.env.CLEF_MCP,
    join(homedir(), ".local", "bin", "clef-mcp"),
    "/opt/homebrew/bin/clef-mcp",
    "/usr/local/bin/clef-mcp",
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (existsSync(candidate)) return [candidate];
  }
  return ["clef-mcp"];
}

export const ClefPlugin = async () => ({
  config: async (config) => {
    config.mcp = config.mcp ?? {};
    config.mcp.clef = {
      type: "local",
      command: resolveClefMcp(),
      enabled: true,
      timeout: 30000,
      environment: {
        CLEF_SERVER_URL: process.env.CLEF_SERVER_URL ?? "http://127.0.0.1:8765",
        CLEF_AUTOSTART: "1",
        PATH: process.env.PATH ?? "",
      },
    };
  },
});
