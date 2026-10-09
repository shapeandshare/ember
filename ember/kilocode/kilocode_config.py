"""Kilo Code integration: write and remove the `mcp.ember` entry in kilo.json.

Kilo Code's MCP config block (``kilo.json`` -> ``mcp.<name>``) uses the same shape
as opencode's: ``type``, ``command``, ``enabled``, ``timeout``, ``environment``. The
entry builder is shared with :mod:`ember.opencode.opencode_config`; only the config
file's name, schema key, and default install paths differ.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..opencode.opencode_config import build_entry, load_config_for_merge

#: The only accepted basename for a kilo config file written or removed by ember.
_ACCEPTED_BASENAME = "kilo.json"


def _validate_config_path(path: Path) -> None:
    """Raise ``ValueError`` unless ``path``'s final component is ``kilo.json``.

    Parameters
    ----------
    path : Path
        The config file path to validate.

    Raises
    ------
    ValueError
        If ``path.name`` is not ``kilo.json``.
    """
    if path.name != _ACCEPTED_BASENAME:
        raise ValueError(
            f"config path must end in {_ACCEPTED_BASENAME!r}; got {path.name!r}"
        )


def global_config_path() -> Path:
    """Return the user-global Kilo Code config path.

    Returns
    -------
    Path
        ``~/.config/kilo/kilo.json``.
    """
    return Path.home() / ".config" / "kilo" / _ACCEPTED_BASENAME


def project_config_path(root: Path) -> Path:
    """Return the project-local Kilo Code config path.

    Parameters
    ----------
    root : Path
        Project root directory.

    Returns
    -------
    Path
        ``<root>/kilo.json``.
    """
    return root / _ACCEPTED_BASENAME


def write(
    path: Path,
    host: str,
    port: int,
    autostart: str,
    server_url: str | None = None,
    auth_header: str | None = None,
) -> Path:
    """Merge the ``mcp.ember`` entry into a Kilo Code config file.

    Preserves any other existing keys in ``path``; creates the file and its
    parent directories if they do not exist.

    Parameters
    ----------
    path : Path
        Config file to read and overwrite. Must end in ``kilo.json``.
    host : str
        Model server host for ``EMBER_SERVER_URL`` when ``server_url`` is not
        given.
    port : int
        Model server port for ``EMBER_SERVER_URL`` when ``server_url`` is not
        given.
    autostart : str
        Value for ``EMBER_AUTOSTART`` (``"1"`` or ``"0"``).
    server_url : str | None, optional
        A remote inference endpoint to bootstrap the client against, in place
        of the local ``http://{host}:{port}`` URL. See
        :func:`ember.opencode.opencode_config.build_entry`.
    auth_header : str | None, optional
        The header name a remote endpoint expects the credential on. Never
        paired with a token value — export ``EMBER_AUTH_TOKEN`` in the shell
        instead.

    Returns
    -------
    Path
        ``path``, after writing.

    Raises
    ------
    ValueError
        If ``path`` does not end in ``kilo.json``, or if it holds content ember
        cannot merge into without losing it (see
        :func:`ember.opencode.opencode_config.load_config_for_merge`); the file
        is left untouched.
    """
    _validate_config_path(path)
    existing = load_config_for_merge(path)
    existing["mcp"]["ember"] = build_entry(
        host, port, autostart, server_url, auth_header
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    # path validated by _validate_config_path above; content is this module's own JSON
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")  # NOSONAR
    os.replace(tmp, path)
    return path


def remove(path: Path) -> bool:
    """Drop the ``mcp.ember`` entry; ``False`` if it is absent or not plain JSON.

    Parameters
    ----------
    path : Path
        Config file to modify. Must end in ``kilo.json``.

    Returns
    -------
    bool
        ``True`` if the entry was present and removed; ``False`` otherwise.

    Raises
    ------
    ValueError
        If ``path`` does not end in ``kilo.json``.
    """
    _validate_config_path(path)
    try:
        existing = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    mcp = existing.get("mcp") if isinstance(existing, dict) else None
    if not isinstance(mcp, dict) or "ember" not in mcp:
        return False
    del existing["mcp"]["ember"]
    tmp = path.with_suffix(".tmp")
    # path validated by _validate_config_path above; content is this module's own JSON
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")  # NOSONAR
    os.replace(tmp, path)
    return True


def has_entry(path: Path) -> bool:
    """Return whether ``path`` registers the ``mcp.ember`` server.

    Read-only: a missing or malformed file counts as not registered.

    Parameters
    ----------
    path : Path
        Config file to inspect. Must end in ``kilo.json``.

    Returns
    -------
    bool
        ``True`` if the file has an ``mcp.ember`` entry.

    Raises
    ------
    ValueError
        If ``path`` does not end in ``kilo.json``.
    """
    _validate_config_path(path)
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    mcp = existing.get("mcp") if isinstance(existing, dict) else None
    return isinstance(mcp, dict) and "ember" in mcp
