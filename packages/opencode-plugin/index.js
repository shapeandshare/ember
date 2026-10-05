// Register the local ember MCP server (the `advise` tool) with opencode.
//
// Register-only: the server stays lazy and is started on first tool call.
// Resolves `ember-mcp` from EMBER_MCP, the uv-tool bin dir, or Homebrew, and
// passes an explicit PATH because opencode launched from a GUI can have a
// stripped environment.
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join, basename } from "node:path";

function resolveEmberMcp() {
  const override = process.env.EMBER_MCP;
  if (override) {
    if (basename(override) !== "ember-mcp") {
      console.error(
        `[ember] EMBER_MCP ignored: basename must be "ember-mcp", got "${basename(override)}". Falling through to standard candidates.`,
      );
    } else if (!existsSync(override)) {
      console.error(
        `[ember] EMBER_MCP ignored: path does not exist: "${override}". Falling through to standard candidates.`,
      );
    } else {
      return [override];
    }
  }
  const standard = [
    join(homedir(), ".local", "bin", "ember-mcp"),
    "/opt/homebrew/bin/ember-mcp",
    "/usr/local/bin/ember-mcp",
  ];
  for (const candidate of standard) {
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
        EMBER_AUTOSTART: process.env.EMBER_AUTOSTART ?? "1",
        PATH: process.env.PATH ?? "",
      },
    };
  },
});
