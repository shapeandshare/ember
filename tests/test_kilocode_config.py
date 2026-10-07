"""Unit tests for kilocode_config path validation and merge behaviour.

Mirrors ``tests/test_opencode_config.py``: covers the ``_validate_config_path``
guard in ``write()`` and ``remove()``, and that ``write()`` merges rather than
clobbers existing ``kilo.json`` content.
"""

from __future__ import annotations

import json
import re

import pytest
from ember.kilocode.kilocode_config import remove, write

_MATCH = re.escape("kilo.json")


def test_write_accepts_kilo_json_basename(tmp_path: pytest.TempPathFactory) -> None:
    """write() must succeed when the path basename is ``kilo.json``."""
    path = tmp_path / "kilo.json"
    result = write(path, "127.0.0.1", 8765, "1")
    assert result == path
    assert path.exists()


def test_write_rejects_non_kilo_json_basename(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """write() must raise ValueError when the basename is not ``kilo.json``."""
    path = tmp_path / "evil.json"
    with pytest.raises(ValueError, match=_MATCH):
        write(path, "127.0.0.1", 8765, "1")


def test_write_rejects_basename_with_traversal_component(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """write() must raise ValueError when the basename is not ``kilo.json``.

    A path like ``../../etc/passwd`` has basename ``passwd``, not ``kilo.json``.
    """
    path = tmp_path / "../../etc/passwd"
    with pytest.raises(ValueError, match=_MATCH):
        write(path, "127.0.0.1", 8765, "1")


def test_write_merges_with_existing_config(tmp_path: pytest.TempPathFactory) -> None:
    """write() must preserve pre-existing keys in kilo.json."""
    path = tmp_path / "kilo.json"
    path.write_text(json.dumps({"model": "keep-me"}))
    write(path, "127.0.0.1", 8765, "1")
    result = json.loads(path.read_text())
    assert result["model"] == "keep-me"
    assert result["mcp"]["ember"]["type"] == "local"


def test_remove_accepts_kilo_json_basename(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """remove() must succeed when basename is kilo.json.

    Returns False because the ember key is absent; no ValueError raised.
    """
    path = tmp_path / "kilo.json"
    result = remove(path)
    assert result is False


def test_remove_rejects_non_kilo_json_basename(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """remove() must raise ValueError when the basename is not ``kilo.json``."""
    path = tmp_path / "evil.json"
    with pytest.raises(ValueError, match=_MATCH):
        remove(path)


def test_remove_rejects_basename_with_traversal_component(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """remove() must raise ValueError when the basename is not ``kilo.json``.

    A path like ``../../etc/passwd`` has basename ``passwd``, not ``kilo.json``.
    """
    path = tmp_path / "../../etc/passwd"
    with pytest.raises(ValueError, match=_MATCH):
        remove(path)


def test_remove_drops_the_ember_entry(tmp_path: pytest.TempPathFactory) -> None:
    """remove() deletes mcp.ember while preserving other mcp entries."""
    path = tmp_path / "kilo.json"
    write(path, "127.0.0.1", 8765, "1")
    assert remove(path) is True
    result = json.loads(path.read_text())
    assert "ember" not in result.get("mcp", {})


def test_write_forwards_server_url_to_the_entry(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """write() plumbs server_url/auth_header through to build_entry()."""
    path = tmp_path / "kilo.json"
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


def test_write_never_embeds_an_auth_token(tmp_path: pytest.TempPathFactory) -> None:
    """write() has no parameter that could embed a secret in kilo.json."""
    path = tmp_path / "kilo.json"
    write(path, "127.0.0.1", 8765, "0", server_url="https://decisions.example.com")
    assert "token" not in path.read_text().lower()
