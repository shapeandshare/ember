"""Unit tests for opencode_config path validation (S2083 hardening) and the
``mcp.ember`` entry builder, including remote-endpoint bootstrap.

Covers the ``_validate_config_path`` guard in ``write()`` and ``remove()``:
- accepted basename (``opencode.json``) must pass through
- any other basename must raise ``ValueError``
"""

from __future__ import annotations

import json
import re

import pytest
from ember.opencode.opencode_config import (
    build_entry,
    has_entry,
    has_legacy_vault_entry,
    remove,
    write,
)

_MATCH = re.escape("opencode.json")
_LEGACY_VAULT = {
    "type": "local",
    "command": ["npx", "-y", "@bitbonsai/mcpvault@0.12.4", "vault"],
    "enabled": True,
}


def test_write_accepts_opencode_json_basename(tmp_path: pytest.TempPathFactory) -> None:
    """write() must succeed when the path basename is ``opencode.json``."""
    path = tmp_path / "opencode.json"
    result = write(path, "127.0.0.1", 8765, "1")
    assert result == path
    assert path.exists()


def test_write_rejects_non_opencode_json_basename(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """write() must raise ValueError when the basename is not ``opencode.json``."""
    path = tmp_path / "evil.json"
    with pytest.raises(ValueError, match=_MATCH):
        write(path, "127.0.0.1", 8765, "1")


def test_write_rejects_basename_with_traversal_component(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """write() must raise ValueError when the basename is not ``opencode.json``.

    A path like ``../../etc/passwd`` has basename ``passwd``, not ``opencode.json``.
    """
    path = tmp_path / "../../etc/passwd"
    with pytest.raises(ValueError, match=_MATCH):
        write(path, "127.0.0.1", 8765, "1")


def test_remove_accepts_opencode_json_basename(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """remove() must succeed when basename is opencode.json.

    Returns False because the ember key is absent; no ValueError raised.
    """
    path = tmp_path / "opencode.json"
    result = remove(path)
    assert result is False


def test_remove_rejects_non_opencode_json_basename(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """remove() must raise ValueError when the basename is not ``opencode.json``."""
    path = tmp_path / "evil.json"
    with pytest.raises(ValueError, match=_MATCH):
        remove(path)


def test_remove_rejects_basename_with_traversal_component(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """remove() must raise ValueError when the basename is not ``opencode.json``.

    A path like ``../../etc/passwd`` has basename ``passwd``, not ``opencode.json``.
    """
    path = tmp_path / "../../etc/passwd"
    with pytest.raises(ValueError, match=_MATCH):
        remove(path)


def test_build_entry_defaults_to_local_loopback_url() -> None:
    """Without server_url, build_entry() targets the local host:port."""
    entry = build_entry("127.0.0.1", 8765, "1")
    assert entry["environment"]["EMBER_SERVER_URL"] == "http://127.0.0.1:8765"
    assert entry["environment"]["EMBER_AUTOSTART"] == "1"
    assert "EMBER_AUTH_HEADER" not in entry["environment"]
    assert "EMBER_AUTH_TOKEN" not in entry["environment"]


def test_build_entry_server_url_overrides_local_host_port() -> None:
    """A remote server_url takes precedence over host/port."""
    entry = build_entry(
        "127.0.0.1", 8765, "1", server_url="https://decisions.example.com"
    )
    assert entry["environment"]["EMBER_SERVER_URL"] == "https://decisions.example.com"


def test_build_entry_never_embeds_an_auth_token() -> None:
    """build_entry() has no parameter that could embed a secret in the file."""
    entry = build_entry(
        "127.0.0.1", 8765, "1", server_url="https://decisions.example.com"
    )
    assert "EMBER_AUTH_TOKEN" not in entry["environment"]
    assert "token" not in str(entry).lower()


def test_build_entry_custom_auth_header_is_recorded_without_a_value() -> None:
    """A custom auth header name is written, but never a credential value."""
    entry = build_entry(
        "127.0.0.1",
        8765,
        "1",
        server_url="https://decisions.example.com",
        auth_header="X-API-KEY",
    )
    assert entry["environment"]["EMBER_AUTH_HEADER"] == "X-API-KEY"
    assert "EMBER_AUTH_TOKEN" not in entry["environment"]


def test_write_forwards_server_url_to_the_entry(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """write() plumbs server_url/auth_header through to build_entry()."""
    path = tmp_path / "opencode.json"
    write(
        path,
        "127.0.0.1",
        8765,
        "0",
        server_url="https://decisions.example.com",
        auth_header="X-API-KEY",
    )
    config = json.loads(path.read_text())
    env = config["mcp"]["ember"]["environment"]
    assert env["EMBER_SERVER_URL"] == "https://decisions.example.com"
    assert env["EMBER_AUTH_HEADER"] == "X-API-KEY"
    assert "EMBER_AUTH_TOKEN" not in env


def test_write_does_not_register_the_vault_server(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """write() registers only ember; the repo's vault server stays in .opencode/."""
    path = tmp_path / "opencode.json"
    write(path, "127.0.0.1", 8765, "1")
    assert "vault" not in json.loads(path.read_text())["mcp"]


def test_write_leaves_an_existing_vault_entry_untouched(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """write() never deletes or rewrites a server entry it does not own."""
    path = tmp_path / "opencode.json"
    custom = {"type": "local", "command": ["my-vault"], "enabled": True}
    path.write_text(json.dumps({"mcp": {"vault": custom}}))
    write(path, "127.0.0.1", 8765, "1")
    assert json.loads(path.read_text())["mcp"]["vault"] == custom


def test_has_entry_is_true_after_write(tmp_path: pytest.TempPathFactory) -> None:
    """has_entry() sees the mcp.ember entry write() produced."""
    path = tmp_path / "opencode.json"
    write(path, "127.0.0.1", 8765, "1")
    assert has_entry(path) is True


@pytest.mark.parametrize(
    "content", ['// comment\n{"model": "x"}', "{not json", "[]", '{"mcp": "x"}']
)
def test_write_refuses_to_replace_a_config_it_cannot_parse(
    tmp_path: pytest.TempPathFactory, content: str
) -> None:
    """write() never clobbers a config it can't merge into; the bytes survive."""
    path = tmp_path / "opencode.json"
    path.write_text(content)
    with pytest.raises(ValueError, match="not overwriting"):
        write(path, "127.0.0.1", 8765, "1")
    assert path.read_text() == content


def test_write_treats_an_empty_file_as_a_new_config(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """An empty opencode.json holds nothing to lose, so write() fills it in."""
    path = tmp_path / "opencode.json"
    path.write_text("")
    write(path, "127.0.0.1", 8765, "1")
    assert has_entry(path) is True


@pytest.mark.parametrize("content", ["[]", '{"mcp": "ember"}'])
def test_remove_is_false_for_a_config_without_an_mcp_table(
    tmp_path: pytest.TempPathFactory, content: str
) -> None:
    """remove() reports nothing removed (and does not crash) on odd JSON shapes."""
    path = tmp_path / "opencode.json"
    path.write_text(content)
    assert remove(path) is False


@pytest.mark.parametrize(
    "content", [None, "{not json", '{"mcp": "ember"}', '["ember"]']
)
def test_has_entry_is_false_for_missing_or_malformed_config(
    tmp_path: pytest.TempPathFactory, content: str | None
) -> None:
    """A missing, unparseable, or oddly shaped file never counts as registered."""
    path = tmp_path / "opencode.json"
    if content is not None:
        path.write_text(content)
    assert has_entry(path) is False


def test_has_entry_rejects_non_opencode_json_basename(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """has_entry() keeps the same basename guard as write() and remove()."""
    with pytest.raises(ValueError, match=_MATCH):
        has_entry(tmp_path / "evil.json")


def test_has_legacy_vault_entry_detects_what_older_inits_wrote(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """The exact mcp.vault entry pre-2026-10-08 `ember init` merged is recognized."""
    path = tmp_path / "opencode.json"
    path.write_text(json.dumps({"mcp": {"vault": _LEGACY_VAULT}}))
    assert has_legacy_vault_entry(path) is True


def test_has_legacy_vault_entry_ignores_a_customized_vault_entry(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """A vault entry the user changed is theirs, not ember's leftover."""
    path = tmp_path / "opencode.json"
    custom = {**_LEGACY_VAULT, "command": ["npx", "-y", "mcpvault", "notes"]}
    path.write_text(json.dumps({"mcp": {"vault": custom}}))
    assert has_legacy_vault_entry(path) is False
