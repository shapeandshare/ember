"""Unit tests for codex_config path validation and TOML merge behaviour.

Mirrors ``tests/test_kilocode_config.py``: covers the ``_validate_config_path``
guard in ``write()`` and ``remove()``, that ``write()`` merges rather than
clobbers existing ``config.toml`` content, and the Codex-specific TOML section
shape (``[mcp_servers.ember]``, ``env_vars``, explicit timeouts).
"""

from __future__ import annotations

import re
import tomllib

import pytest
from ember.codex.codex_config import (
    global_config_path,
    has_entry,
    project_config_path,
    remove,
    write,
)

_MATCH = re.escape("config.toml")


def test_write_accepts_config_toml_basename(tmp_path: pytest.TempPathFactory) -> None:
    """write() must succeed when the path basename is ``config.toml``."""
    path = tmp_path / "config.toml"
    result = write(path, "127.0.0.1", 8765, "1")
    assert result == path
    assert path.exists()


@pytest.mark.parametrize("bad_name", ["evil.toml", "config.json"])
def test_write_rejects_non_config_toml_basename(
    tmp_path: pytest.TempPathFactory, bad_name: str
) -> None:
    """write() must raise ValueError when the basename is not ``config.toml``."""
    path = tmp_path / bad_name
    with pytest.raises(ValueError, match=_MATCH):
        write(path, "127.0.0.1", 8765, "1")


def test_write_rejects_basename_with_traversal_component(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """A path like ``../../etc/passwd`` has basename ``passwd``, not ``config.toml``."""
    path = tmp_path / "../../etc/passwd"
    with pytest.raises(ValueError, match=_MATCH):
        write(path, "127.0.0.1", 8765, "1")


def test_write_fresh_file_has_expected_ember_section(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """A fresh write() produces a parseable `[mcp_servers.ember]` with every field."""
    path = tmp_path / "config.toml"
    write(path, "127.0.0.1", 8765, "1")
    parsed = tomllib.loads(path.read_text())
    entry = parsed["mcp_servers"]["ember"]
    assert entry["command"]
    assert entry["env"]["EMBER_SERVER_URL"] == "http://127.0.0.1:8765"
    assert entry["env"]["EMBER_AUTOSTART"] == "1"
    assert "EMBER_AUTH_TOKEN" in entry["env_vars"]
    assert entry["enabled"] is True
    assert entry["startup_timeout_sec"] == 30
    assert entry["tool_timeout_sec"] == 300


def test_write_merges_with_existing_config(tmp_path: pytest.TempPathFactory) -> None:
    """write() must preserve pre-existing keys, an unrelated section, and a comment."""
    path = tmp_path / "config.toml"
    path.write_text(
        "# my codex config\n"
        'model = "keep-me"\n'
        "\n"
        "[mcp_servers.other]\n"
        'command = "other-server"\n'
    )
    write(path, "127.0.0.1", 8765, "1")
    text = path.read_text()
    assert "# my codex config" in text
    parsed = tomllib.loads(text)
    assert parsed["model"] == "keep-me"
    assert parsed["mcp_servers"]["other"]["command"] == "other-server"
    assert parsed["mcp_servers"]["ember"]["enabled"] is True


def test_write_twice_leaves_exactly_one_ember_section(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """A second write() with a different port replaces, not duplicates, the section."""
    path = tmp_path / "config.toml"
    write(path, "127.0.0.1", 8765, "1")
    write(path, "127.0.0.1", 9999, "1")
    text = path.read_text()
    assert text.count("[mcp_servers.ember") == 1
    parsed = tomllib.loads(text)
    assert parsed["mcp_servers"]["ember"]["env"]["EMBER_SERVER_URL"] == (
        "http://127.0.0.1:9999"
    )


def test_write_forwards_server_url_and_auth_header_never_a_token(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """write() plumbs server_url/auth_header through; never writes a token value."""
    path = tmp_path / "config.toml"
    write(
        path,
        "127.0.0.1",
        8765,
        "0",
        server_url="https://decisions.example.com",
        auth_header="X-API-KEY",
    )
    text = path.read_text()
    parsed = tomllib.loads(text)
    entry = parsed["mcp_servers"]["ember"]
    assert entry["env"]["EMBER_SERVER_URL"] == "https://decisions.example.com"
    assert entry["env"]["EMBER_AUTH_HEADER"] == "X-API-KEY"
    assert "EMBER_AUTH_TOKEN" not in entry["env"]
    assert entry["env_vars"] == ["EMBER_AUTH_TOKEN"]
    assert text.count("EMBER_AUTH_TOKEN") == 1


def test_write_rejects_malformed_existing_toml_and_leaves_file_untouched(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """A malformed existing config.toml raises ValueError; bytes are unchanged."""
    path = tmp_path / "config.toml"
    original = "this = is [ not valid toml"
    path.write_text(original)
    with pytest.raises(ValueError, match="invalid TOML"):
        write(path, "127.0.0.1", 8765, "1")
    assert path.read_text() == original


def test_remove_drops_the_ember_entry_keeps_other_server_and_comment(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """remove() deletes [mcp_servers.ember]; other entries/comments survive."""
    path = tmp_path / "config.toml"
    path.write_text(
        '# my codex config\n[mcp_servers.other]\ncommand = "other-server"\n'
    )
    write(path, "127.0.0.1", 8765, "1")
    assert remove(path) is True
    text = path.read_text()
    assert "# my codex config" in text
    parsed = tomllib.loads(text)
    assert parsed["mcp_servers"]["other"]["command"] == "other-server"
    assert "ember" not in parsed.get("mcp_servers", {})


def test_remove_returns_false_when_absent(tmp_path: pytest.TempPathFactory) -> None:
    """remove() returns False when the file does not exist."""
    path = tmp_path / "config.toml"
    assert remove(path) is False


def test_remove_rejects_non_config_toml_basename(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """remove() must raise ValueError when the basename is not ``config.toml``."""
    path = tmp_path / "evil.toml"
    with pytest.raises(ValueError, match=_MATCH):
        remove(path)


def test_remove_returns_false_on_malformed_toml(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """remove() is lenient: malformed TOML returns False rather than raising."""
    path = tmp_path / "config.toml"
    path.write_text("this = is [ not valid toml")
    assert remove(path) is False


def test_remove_leaves_a_section_it_cannot_strip_cleanly_untouched(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """A hand-edited ember section whose value lines start with ``[`` survives."""
    path = tmp_path / "config.toml"
    original = '[mcp_servers.ember]\ncommand = "x"\nargs = [\n["nested"]\n]\n'
    path.write_text(original)
    assert remove(path) is False
    assert path.read_text() == original


def test_global_config_path_honors_codex_home(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """global_config_path() prefers CODEX_HOME when set and non-empty."""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "custom-codex"))
    assert global_config_path() == tmp_path / "custom-codex" / "config.toml"


def test_global_config_path_falls_back_to_dot_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """global_config_path() falls back to ~/.codex/config.toml when unset."""
    monkeypatch.delenv("CODEX_HOME", raising=False)
    from pathlib import Path

    assert global_config_path() == Path.home() / ".codex" / "config.toml"


def test_project_config_path_is_dot_codex_under_root(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """project_config_path() is <root>/.codex/config.toml."""
    assert project_config_path(tmp_path) == tmp_path / ".codex" / "config.toml"


def test_write_inline_ember_entry_raises_value_error_and_leaves_file(tmp_path):
    target = tmp_path / "config.toml"
    original = '[mcp_servers]\nember = { command = "x" }\n'
    target.write_text(original)
    with pytest.raises(ValueError, match=re.escape("mcp_servers.ember")):
        write(target, "127.0.0.1", 8765, "1")
    assert target.read_text() == original


def test_rewrite_keeps_comment_that_precedes_the_next_table(tmp_path):
    target = tmp_path / "config.toml"
    write(target, "127.0.0.1", 8765, "1")
    target.write_text(
        target.read_text()
        + '\n# keep me: describes other\n[mcp_servers.other]\ncommand = "o"\n'
    )
    write(target, "127.0.0.1", 8765, "1")
    assert "# keep me: describes other\n[mcp_servers.other]" in target.read_text()


def test_has_entry_is_true_after_write(tmp_path: pytest.TempPathFactory) -> None:
    """has_entry() sees the [mcp_servers.ember] section write() produced."""
    path = tmp_path / "config.toml"
    write(path, "127.0.0.1", 8765, "1")
    assert has_entry(path) is True


def test_has_entry_detects_a_hand_written_inline_table(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Detection reads parsed TOML, so any valid form of the entry counts."""
    path = tmp_path / "config.toml"
    path.write_text('[mcp_servers]\nember = { command = "ember-mcp" }\n')
    assert has_entry(path) is True


@pytest.mark.parametrize(
    "content", [None, "this = is [ not valid toml", 'mcp_servers = "ember"']
)
def test_has_entry_is_false_for_missing_or_malformed_config(
    tmp_path: pytest.TempPathFactory, content: str | None
) -> None:
    """A missing, unparseable, or oddly shaped config.toml is not registered."""
    path = tmp_path / "config.toml"
    if content is not None:
        path.write_text(content)
    assert has_entry(path) is False
