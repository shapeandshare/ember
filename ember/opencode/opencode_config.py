"""OpenCode integration: write, merge, and remove the `mcp.ember` config entry."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

SCHEMA = "https://opencode.ai/config.json"

#: The only accepted basename for an opencode config file written or removed by ember.
_ACCEPTED_BASENAME = "opencode.json"

#: The ``mcp.vault`` entry ``ember init`` merged into every config it wrote before
#: 2026-10-08. ember no longer writes it; it is kept only so ``ember doctor`` can
#: point users at a leftover copy, never to delete one automatically.
_LEGACY_VAULT_ENTRY: dict[str, Any] = {
    "type": "local",
    "command": ["npx", "-y", "@bitbonsai/mcpvault@0.12.4", "vault"],
    "enabled": True,
}


def _validate_config_path(path: Path) -> None:
    """Raise ``ValueError`` unless ``path``'s final component is ``opencode.json``.

    This is the path-traversal sanitizer for the S2083 findings: callers
    (``write`` and ``remove``) only ever produce paths whose basename is
    ``opencode.json``, so any other value indicates unexpected or attacker-
    controlled input.

    Parameters
    ----------
    path : Path
        The config file path to validate.

    Raises
    ------
    ValueError
        If ``path.name`` is not ``opencode.json``.
    """
    if path.name != _ACCEPTED_BASENAME:
        raise ValueError(
            f"config path must end in {_ACCEPTED_BASENAME!r}; got {path.name!r}"
        )


def global_config_path() -> Path:
    """Return the user-global opencode config path.

    Returns
    -------
    Path
        ``~/.config/opencode/opencode.json``.
    """
    return Path.home() / ".config" / "opencode" / _ACCEPTED_BASENAME


def project_config_path(root: Path) -> Path:
    """Return the project-local opencode config path.

    Parameters
    ----------
    root : Path
        Project root directory.

    Returns
    -------
    Path
        ``<root>/opencode.json``.
    """
    return root / _ACCEPTED_BASENAME


def mcp_command() -> list[str]:
    """Prefer the installed console script; fall back to this interpreter + module."""
    exe = shutil.which("ember-mcp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "ember.mcp.mcp_server"]


def build_entry(
    host: str,
    port: int,
    autostart: str,
    server_url: str | None = None,
    auth_header: str | None = None,
) -> dict[str, Any]:
    """Build the ``mcp.ember`` entry for an opencode or Kilo Code config file.

    The two tools share the same MCP entry shape, so
    :mod:`ember.kilocode.kilocode_config` reuses this builder for ``kilo.json``.

    Never embeds a credential: a bootstrapped remote entry names the header to
    send (``EMBER_AUTH_HEADER``) but leaves ``EMBER_AUTH_TOKEN`` for the user to
    export in their shell, so a secret is never written to a config file that
    may be project-committed (constitution: avoid secrets at rest in VCS).

    Parameters
    ----------
    host : str
        Model server host for ``EMBER_SERVER_URL`` when ``server_url`` is not
        given.
    port : int
        Model server port for ``EMBER_SERVER_URL`` when ``server_url`` is not
        given.
    autostart : str
        Value for ``EMBER_AUTOSTART`` (``"1"`` or ``"0"``).
    server_url : str | None, optional
        A remote inference endpoint. When given, it replaces the local
        ``http://{host}:{port}`` URL — bootstrapping a client against a
        hosted server instead of a local one.
    auth_header : str | None, optional
        The header name a remote endpoint expects the credential on (e.g.
        ``"X-API-KEY"``). Only written when ``server_url`` is given. Never
        paired with a token value — export ``EMBER_AUTH_TOKEN`` in the shell
        that launches the agent instead.

    Returns
    -------
    dict[str, Any]
        The ``mcp.ember`` entry.
    """
    environment = {
        "EMBER_SERVER_URL": server_url or f"http://{host}:{port}",  # NOSONAR
        "EMBER_AUTOSTART": autostart,
    }
    if server_url and auth_header:
        environment["EMBER_AUTH_HEADER"] = auth_header
    return {
        "type": "local",
        "command": mcp_command(),
        "enabled": True,
        "timeout": 30000,
        "environment": environment,
    }


def write(
    path: Path,
    host: str,
    port: int,
    autostart: str,
    server_url: str | None = None,
    auth_header: str | None = None,
) -> Path:
    """Merge the ``mcp.ember`` entry into an opencode config file.

    Preserves any other existing keys in ``path``; creates the file and its
    parent directories if they do not exist. Registers only ember: servers a
    repository shares with its contributors (such as this repo's ``vault``)
    belong in the committed ``.opencode/opencode.json``, never in a generated
    client config.

    Parameters
    ----------
    path : Path
        Config file to read and overwrite.  Must end in ``opencode.json``.
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
        of the local ``http://{host}:{port}`` URL. See ``build_entry``.
    auth_header : str | None, optional
        The header name a remote endpoint expects the credential on. See
        ``build_entry``; never paired with a token value.

    Returns
    -------
    Path
        ``path``, after writing.

    Raises
    ------
    ValueError
        If ``path`` does not end in ``opencode.json``, or if it holds content
        ember cannot merge into without losing it (see
        ``load_config_for_merge``); the file is left untouched.
    """
    _validate_config_path(path)
    existing = load_config_for_merge(path)
    existing.setdefault("$schema", SCHEMA)
    existing["mcp"]["ember"] = build_entry(
        host, port, autostart, server_url, auth_header
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_config_for_merge(path: Path) -> dict[str, Any]:
    """Return an opencode-style config to merge into, refusing lossy rewrites.

    Shared with :mod:`ember.kilocode.kilocode_config` (``kilo.json`` has the
    same shape). Rewriting a file ember cannot parse, such as one with
    comments, would silently drop the user's settings, so that is an error.

    Parameters
    ----------
    path : Path
        Config file to read; a missing or empty file counts as a new config.

    Returns
    -------
    dict[str, Any]
        The parsed config, holding an ``mcp`` mapping ready for the entry.

    Raises
    ------
    ValueError
        If the file is not plain JSON, is not a JSON object, or has an ``mcp``
        value that is not an object.
    """
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if not text.strip():
        return {"mcp": {}}
    try:
        existing = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path} is not plain JSON ({exc.msg}, line {exc.lineno}); not "
            "overwriting it. Fix the file, or add the mcp.ember entry by hand."
        ) from exc
    if not isinstance(existing, dict) or not isinstance(
        existing.setdefault("mcp", {}), dict
    ):
        raise ValueError(
            f"{path} is not a config object with an mcp table; not overwriting it."
        )
    return existing


def remove(path: Path) -> bool:
    """Drop the ``mcp.ember`` entry; ``False`` if it is absent or not plain JSON.

    Parameters
    ----------
    path : Path
        Config file to modify.  Must end in ``opencode.json``.

    Returns
    -------
    bool
        ``True`` if the entry was present and removed; ``False`` otherwise.

    Raises
    ------
    ValueError
        If ``path`` does not end in ``opencode.json``.
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
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return True


def _read_mcp(path: Path) -> dict[str, Any]:
    """Return the ``mcp`` table of an opencode config, or ``{}``.

    Parameters
    ----------
    path : Path
        Config file to read.

    Returns
    -------
    dict[str, Any]
        The ``mcp`` mapping; empty when the file is missing, unreadable, not
        JSON, or not shaped like a config.
    """
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    mcp = existing.get("mcp") if isinstance(existing, dict) else None
    return mcp if isinstance(mcp, dict) else {}


def has_entry(path: Path) -> bool:
    """Return whether ``path`` registers the ``mcp.ember`` server.

    Read-only: a missing or malformed file counts as not registered.

    Parameters
    ----------
    path : Path
        Config file to inspect. Must end in ``opencode.json``.

    Returns
    -------
    bool
        ``True`` if the file has an ``mcp.ember`` entry.

    Raises
    ------
    ValueError
        If ``path`` does not end in ``opencode.json``.
    """
    _validate_config_path(path)
    return "ember" in _read_mcp(path)


def has_legacy_vault_entry(path: Path) -> bool:
    """Return whether ``path`` still holds the ``mcp.vault`` entry old inits wrote.

    Parameters
    ----------
    path : Path
        Config file to inspect. Must end in ``opencode.json``.

    Returns
    -------
    bool
        ``True`` only for an exact copy of the legacy entry; a vault entry the
        user changed is theirs and is not reported.

    Raises
    ------
    ValueError
        If ``path`` does not end in ``opencode.json``.
    """
    _validate_config_path(path)
    return _read_mcp(path).get("vault") == _LEGACY_VAULT_ENTRY
