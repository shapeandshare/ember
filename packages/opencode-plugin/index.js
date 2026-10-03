// Register the local gut-feeling MCP server (the `advise` tool) with opencode.
//
// Register-only: the server stays lazy and is started on first tool call.
// Resolves `gut-feeling-mcp` from GUT_FEELING_MCP, the uv-tool bin dir, or Homebrew, and
// passes an explicit PATH because opencode launched from a GUI can have a
// stripped environment.
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function resolveGutFeelingMcp() {
  const candidates = [
    process.env.GUT_FEELING_MCP,
    join(homedir(), ".local", "bin", "gut-feeling-mcp"),
    "/opt/homebrew/bin/gut-feeling-mcp",
    "/usr/local/bin/gut-feeling-mcp",
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (existsSync(candidate)) return [candidate];
  }
  return ["gut-feeling-mcp"];
}

export const GutFeelingPlugin = async () => ({
  config: async (config) => {
    config.mcp = config.mcp ?? {};
    config.mcp["gut-feeling"] = {
      type: "local",
      command: resolveGutFeelingMcp(),
      enabled: true,
      timeout: 30000,
      environment: {
        GUT_FEELING_SERVER_URL: process.env.GUT_FEELING_SERVER_URL ?? "http://127.0.0.1:8765",
        GUT_FEELING_AUTOSTART: "1",
        PATH: process.env.PATH ?? "",
      },
    };
  },
});
