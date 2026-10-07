"""Unit tests for opencode_config path validation (S2083 hardening) and the
``mcp.ember`` entry builder, including remote-endpoint bootstrap.

Covers the ``_validate_config_path`` guard in ``write()`` and ``remove()``:
- accepted basename (``opencode.json``) must pass through
- any other basename must raise ``ValueError``
"""

from __future__ import annotations

import re

import pytest
from ember.opencode.opencode_config import build_entry, remove, write

_MATCH = re.escape("opencode.json")


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
    import json

    config = json.loads(path.read_text())
    env = config["mcp"]["ember"]["environment"]
    assert env["EMBER_SERVER_URL"] == "https://decisions.example.com"
    assert env["EMBER_AUTH_HEADER"] == "X-API-KEY"
    assert "EMBER_AUTH_TOKEN" not in env
