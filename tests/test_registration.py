"""Unit tests for the per-harness registration report shown by ``ember doctor``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ember.claude import claude_config
from ember.codex import codex_config
from ember.commands import registration
from ember.kilocode import kilocode_config
from ember.opencode import opencode_config, opencode_plugin

_LEGACY_VAULT = {
    "type": "local",
    "command": ["npx", "-y", "@bitbonsai/mcpvault@0.12.4", "vault"],
    "enabled": True,
}


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(registration.shutil, "which", lambda name: None)
    root = tmp_path / "project"
    root.mkdir()
    return root


def _report(root: Path) -> dict[str, str]:
    return dict(registration.registration_lines(root))


@pytest.mark.parametrize(
    ("harness", "hint"),
    [
        ("opencode", "`ember init --opencode`"),
        ("kilo", "`ember init --kilocode`"),
        ("codex", "`ember init --codex`"),
        ("claude", "`claude mcp add --scope user ember -- ember-mcp`"),
    ],
)
def test_each_unregistered_harness_names_its_registration_command(
    project: Path, harness: str, hint: str
) -> None:
    detail = _report(project)[f"{harness} registration"]
    assert detail.startswith("none — run ")
    assert hint in detail


def test_binary_lines_report_the_path_or_its_absence(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        registration.shutil,
        "which",
        lambda name: f"/bin/{name}" if name == "codex" else None,
    )
    report = _report(project)
    assert (report["codex"], report["opencode"]) == ("/bin/codex", "not on PATH")


def test_opencode_reports_a_project_config_and_a_global_plugin(project: Path) -> None:
    config = opencode_config.project_config_path(project)
    opencode_config.write(config, "127.0.0.1", 8765, "1")
    plugin = opencode_plugin.install(["ember-mcp"], "http://127.0.0.1:8765", "global")
    detail = _report(project)["opencode registration"]
    assert detail == f"project config {config}; global plugin {plugin}"


def test_kilo_reports_a_global_registration(project: Path) -> None:
    config = kilocode_config.global_config_path()
    kilocode_config.write(config, "127.0.0.1", 8765, "1")
    assert _report(project)["kilo registration"] == f"global {config}"


def test_codex_flags_a_project_registration_it_will_ignore(project: Path) -> None:
    codex_config.write(
        codex_config.project_config_path(project), "127.0.0.1", 8765, "1"
    )
    assert "until you trust this project" in _report(project)["codex registration"]


def test_codex_names_the_file_for_an_explicitly_untrusted_project(
    project: Path,
) -> None:
    codex_config.write(
        codex_config.project_config_path(project), "127.0.0.1", 8765, "1"
    )
    trust = codex_config.global_config_path()
    trust.parent.mkdir(parents=True)
    trust.write_text(
        f'[projects.{json.dumps(str(project.resolve()))}]\ntrust_level = "untrusted"\n'
    )
    assert f"marked untrusted in {trust}" in _report(project)["codex registration"]


def test_codex_accepts_a_trusted_project_registration(project: Path) -> None:
    config = codex_config.project_config_path(project)
    codex_config.write(config, "127.0.0.1", 8765, "1")
    trust = codex_config.global_config_path()
    trust.parent.mkdir(parents=True)
    trust.write_text(
        f'[projects.{json.dumps(str(project.resolve()))}]\ntrust_level = "trusted"\n'
    )
    assert _report(project)["codex registration"] == f"project {config}"


def test_claude_reports_user_and_local_scopes(project: Path) -> None:
    user = claude_config.user_config_path()
    user.parent.mkdir(parents=True, exist_ok=True)
    servers = {"mcpServers": {"ember": {}}}
    user.write_text(json.dumps({**servers, "projects": {str(project): servers}}))
    detail = _report(project)["claude registration"]
    assert detail == f"user {user}; local {user} (this project)"


def test_claude_says_a_project_mcp_json_needs_approval(project: Path) -> None:
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"ember": {}}}))
    assert "approve it when Claude Code asks" in _report(project)["claude registration"]


def test_a_leftover_global_vault_entry_gets_a_cleanup_hint(project: Path) -> None:
    config = opencode_config.global_config_path()
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"mcp": {"vault": _LEGACY_VAULT}}))
    assert str(config) in _report(project)["opencode legacy"]


def test_there_is_no_legacy_line_without_a_leftover_vault_entry(project: Path) -> None:
    assert "opencode legacy" not in _report(project)
