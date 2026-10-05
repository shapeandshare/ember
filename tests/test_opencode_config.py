"""Unit tests for opencode_config path validation (S2083 hardening).

Covers the ``_validate_config_path`` guard in ``write()`` and ``remove()``:
- accepted basename (``opencode.json``) must pass through
- any other basename must raise ``ValueError``
"""

from __future__ import annotations

import re

import pytest
from ember.opencode.opencode_config import remove, write

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
