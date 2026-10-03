// Register the local ember MCP server (the `advise` tool) with opencode.
//
// Register-only: the server stays lazy and is started on first tool call.
// Resolves `ember-mcp` from EMBER_MCP, the uv-tool bin dir, or Homebrew, and
// passes an explicit PATH because opencode launched from a GUI can have a
// stripped environment.
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function resolveEmberMcp() {
  const candidates = [
    process.env.EMBER_MCP,
    join(homedir(), ".local", "bin", "ember-mcp"),
    "/opt/homebrew/bin/ember-mcp",
    "/usr/local/bin/ember-mcp",
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (existsSync(candidate)) return [candidate];
  }
  return ["ember-mcp"];
}

export const EmberPlugin = async () => ({
  config: async (config) => {
    config.mcp = config.mcp ?? {};
    config.mcp["ember"] = {
      type: "local",
      command: resolveEmberMcp(),
      enabled: true,
      timeout: 30000,
      environment: {
        EMBER_SERVER_URL: process.env.EMBER_SERVER_URL ?? "http://127.0.0.1:8765",
        EMBER_AUTOSTART: "1",
        PATH: process.env.PATH ?? "",
      },
    };
  },
});
