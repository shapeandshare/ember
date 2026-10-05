// Tests for the npm plugin's config hook.
// Run: node --test packages/opencode-plugin/
import { test } from "node:test";
import assert from "node:assert/strict";

import { EmberPlugin } from "./index.js";

async function pluginEnvironment() {
  const config = {};
  const plugin = await EmberPlugin();
  await plugin.config(config);
  return config.mcp.ember.environment;
}

async function withEnv(name, value, fn) {
  const previous = process.env[name];
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
  try {
    return await fn();
  } finally {
    if (previous === undefined) delete process.env[name];
    else process.env[name] = previous;
  }
}

test("defaults EMBER_AUTOSTART to 1 so the server starts on first call", async () => {
  const env = await withEnv("EMBER_AUTOSTART", undefined, pluginEnvironment);
  assert.equal(env.EMBER_AUTOSTART, "1");
});

test("respects an EMBER_AUTOSTART override from the environment", async () => {
  const env = await withEnv("EMBER_AUTOSTART", "0", pluginEnvironment);
  assert.equal(env.EMBER_AUTOSTART, "0");
});

test("defaults EMBER_SERVER_URL to the loopback server", async () => {
  const env = await withEnv("EMBER_SERVER_URL", undefined, pluginEnvironment);
  assert.equal(env.EMBER_SERVER_URL, "http://127.0.0.1:8765");
});

test("respects an EMBER_SERVER_URL override from the environment", async () => {
  const env = await withEnv(
    "EMBER_SERVER_URL",
    "http://127.0.0.1:9999",
    pluginEnvironment,
  );
  assert.equal(env.EMBER_SERVER_URL, "http://127.0.0.1:9999");
});

// E-002: EMBER_MCP basename validation
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join as pathJoin, basename } from "node:path";

async function pluginCommand() {
  const config = {};
  const plugin = await EmberPlugin();
  await plugin.config(config);
  return config.mcp.ember.command;
}

async function withEnvAndFile(envName, filePath, fn) {
  return withEnv(envName, filePath, fn);
}

test("valid EMBER_MCP override with correct basename wins over standard candidates", async () => {
  const dir = mkdtempSync(pathJoin(tmpdir(), "ember-test-"));
  const validPath = pathJoin(dir, "ember-mcp");
  writeFileSync(validPath, "#!/bin/sh\n", { mode: 0o755 });
  const command = await withEnvAndFile("EMBER_MCP", validPath, pluginCommand);
  assert.equal(command[0], validPath);
});

test("EMBER_MCP with wrong basename is ignored and falls through to standard candidates", async () => {
  const dir = mkdtempSync(pathJoin(tmpdir(), "ember-test-"));
  const wrongPath = pathJoin(dir, "malicious-binary");
  writeFileSync(wrongPath, "#!/bin/sh\n", { mode: 0o755 });
  const command = await withEnvAndFile("EMBER_MCP", wrongPath, pluginCommand);
  assert.notEqual(command[0], wrongPath, "wrong-basename override must be ignored");
});

test("EMBER_MCP pointing to a nonexistent file is ignored and falls through", async () => {
  const command = await withEnv("EMBER_MCP", "/nonexistent/path/ember-mcp", pluginCommand);
  assert.notEqual(command[0], "/nonexistent/path/ember-mcp");
});

test("EMBER_MCP with correct basename but nonexistent file is ignored", async () => {
  const command = await withEnv("EMBER_MCP", "/nonexistent/ember-mcp", pluginCommand);
  assert.notEqual(command[0], "/nonexistent/ember-mcp");
});
