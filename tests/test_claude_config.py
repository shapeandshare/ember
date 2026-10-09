"""Unit tests for read-only Claude Code MCP registration detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ember.claude.claude_config import (
    PLUGIN_ID,
    has_local_entry,
    has_project_entry,
    has_user_entry,
    plugin_scopes,
    project_config_path,
    user_config_path,
)

_EMBER = {"type": "stdio", "command": "ember-mcp", "args": []}


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return home


def test_user_config_path_defaults_to_home_dot_claude_json(home: Path) -> None:
    assert user_config_path() == home / ".claude.json"


def test_user_config_path_honors_claude_config_dir(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert user_config_path() == tmp_path / "cfg" / ".claude.json"


def test_has_user_entry_reads_top_level_mcp_servers(home: Path) -> None:
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {"ember": _EMBER}}))
    assert has_user_entry() is True


def test_has_local_entry_reads_this_projects_entry(tmp_path: Path, home: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = {"projects": {str(project): {"mcpServers": {"ember": _EMBER}}}}
    (home / ".claude.json").write_text(json.dumps(config))
    assert has_local_entry(project) is True


def test_has_local_entry_keys_by_repository_root_from_a_subdirectory(
    tmp_path: Path, home: Path
) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    sub = repo / "pkg"
    sub.mkdir()
    config = {"projects": {str(repo): {"mcpServers": {"ember": _EMBER}}}}
    (home / ".claude.json").write_text(json.dumps(config))
    assert has_local_entry(sub) is True


def test_has_local_entry_ignores_other_projects(tmp_path: Path, home: Path) -> None:
    config = {"projects": {"/somewhere/else": {"mcpServers": {"ember": _EMBER}}}}
    (home / ".claude.json").write_text(json.dumps(config))
    assert has_local_entry(tmp_path) is False


def test_project_config_path_is_dot_mcp_json_at_the_repository_root(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "pkg"
    sub.mkdir()
    assert project_config_path(sub) == tmp_path / ".mcp.json"


def test_has_project_entry_reads_dot_mcp_json(tmp_path: Path) -> None:
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"ember": _EMBER}}))
    assert has_project_entry(tmp_path) is True


@pytest.mark.parametrize("content", [None, "{nope", '{"mcpServers": []}', "[1]"])
def test_detection_is_false_for_missing_or_malformed_files(
    tmp_path: Path, home: Path, content: str | None
) -> None:
    for path in (home / ".claude.json", tmp_path / ".mcp.json"):
        if content is not None:
            path.write_text(content)
    found = (has_user_entry(), has_local_entry(tmp_path), has_project_entry(tmp_path))
    assert found == (False, False, False)


def _enable(settings: Path, enabled: bool) -> None:
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"enabledPlugins": {PLUGIN_ID: enabled}}))


def test_plugin_scopes_reads_user_settings(tmp_path: Path, home: Path) -> None:
    _enable(home / ".claude" / "settings.json", True)
    assert plugin_scopes(tmp_path) == [("user", home / ".claude" / "settings.json")]


def test_plugin_scopes_honors_claude_config_dir(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    _enable(tmp_path / "cfg" / "settings.json", True)
    assert plugin_scopes(tmp_path) == [("user", tmp_path / "cfg" / "settings.json")]


def test_plugin_scopes_reads_project_settings_at_the_repository_root(
    tmp_path: Path, home: Path
) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    _enable(repo / ".claude" / "settings.json", True)
    assert plugin_scopes(repo / "sub") == [
        ("project", repo / ".claude" / "settings.json")
    ]


def test_plugin_scopes_lets_local_settings_disable_the_plugin(
    tmp_path: Path, home: Path
) -> None:
    _enable(home / ".claude" / "settings.json", True)
    _enable(tmp_path / ".claude" / "settings.local.json", False)
    assert plugin_scopes(tmp_path) == []
