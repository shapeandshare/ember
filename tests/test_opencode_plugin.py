"""Tests for the generated opencode plugin (no model, no external processes)."""

from __future__ import annotations

from gut_feeling import opencode_plugin


def test_render_injects_command_and_environment(monkeypatch):
    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin")
    output = opencode_plugin.render(["/x/gut-feeling-mcp"], "http://127.0.0.1:8765")
    assert '"/x/gut-feeling-mcp"' in output
    assert "http://127.0.0.1:8765" in output
    assert "GUT_FEELING_AUTOSTART" in output
    assert "/opt/homebrew/bin" in output
    assert 'config.mcp["gut-feeling"]' in output


def test_install_project_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/bin")
    path = opencode_plugin.install(
        ["/x/gut-feeling-mcp"],
        "http://127.0.0.1:9000",
        scope="project",
        project_root=tmp_path,
    )
    assert path.name == "gut-feeling.js"
    assert path.parent == tmp_path / ".opencode" / "plugins"
    text = path.read_text()
    assert "/x/gut-feeling-mcp" in text
    assert "9000" in text
