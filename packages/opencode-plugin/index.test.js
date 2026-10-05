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
