"""Tests for the generated opencode plugin (no model, no external processes)."""

from __future__ import annotations

from ember import opencode_plugin


def test_render_injects_command_and_environment(monkeypatch):
    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin")
    output = opencode_plugin.render(["/x/ember-mcp"], "http://127.0.0.1:8765")
    assert '"/x/ember-mcp"' in output
    assert "http://127.0.0.1:8765" in output
    assert "EMBER_AUTOSTART" in output
    assert "/opt/homebrew/bin" in output
    assert 'config.mcp["ember"]' in output


def test_install_project_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/bin")
    path = opencode_plugin.install(
        ["/x/ember-mcp"],
        "http://127.0.0.1:9000",
        scope="project",
        project_root=tmp_path,
    )
    assert path.name == "ember.js"
    assert path.parent == tmp_path / ".opencode" / "plugins"
    text = path.read_text()
    assert "/x/ember-mcp" in text
    assert "9000" in text
