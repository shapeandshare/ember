"""Codex CLI integration: write and remove the `[mcp_servers.ember]` section.

Codex CLI (https://github.com/openai/codex) reads its MCP server registrations from
``config.toml`` — a user-global file (``~/.codex/config.toml``, or
``$CODEX_HOME/config.toml`` when ``CODEX_HOME`` is set and non-empty) and, for
trusted projects only, a project-local ``<repo>/.codex/config.toml``.

This module renders and merges the ``[mcp_servers.ember]`` section by hand instead
of depending on a TOML-writing library:

- **No new dependency.** ember has no TOML writer in its dependency graph (only the
  stdlib ``tomllib`` reader, 3.11+). Adding one (``tomli-w``, ``tomlkit``) for a
  single config section is unjustified — constitution Article XV (YAGNI).
- **Section-merge, not full re-serialization.** A full parse-mutate-dump round trip
  would need a TOML *writer* able to reproduce the user's existing comments, key
  order, and formatting, which ``tomllib`` cannot do (it is read-only). Instead this
  module treats the ember section as an opaque, clearly-delimited block: it is
  located by its header line(s) and spliced out textually, and a freshly rendered
  block is appended. Everything else in the file — comments, unrelated tables, key
  order — survives byte-for-byte.
- **``env_vars`` forwards the token by name, never by value.** Codex does not
  inherit arbitrary parent environment variables into an MCP server subprocess
  (only a fixed whitelist: ``HOME``, ``PATH``, ``SHELL``, ``USER``, ``TMPDIR``,
  ...). The only way for a shell-exported ``EMBER_AUTH_TOKEN`` to reach the ember
  MCP child is to list its *name* in ``env_vars``; the entry never contains the
  token's value, so a secret is never persisted to a config file that might be
  project-committed.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path

from ..opencode.opencode_config import mcp_command

#: The only accepted basename for a Codex config file written or removed by ember.
_ACCEPTED_BASENAME = "config.toml"

#: The `[mcp_servers.<key>]` table name ember owns.
_SERVER_KEY = "ember"

#: Env var name Codex forwards from its own process env into the MCP child, never
#: written by value — see the module docstring.
_AUTH_ENV_VAR = "EMBER_AUTH_TOKEN"

#: Explicit timeouts (Codex's own documented/code-path defaults disagree; pin ours).
#: The tool timeout matches ember's default request timeout, so Codex never gives up
#: on a request that ember is still waiting for.
_STARTUP_TIMEOUT_SEC = 30
_TOOL_TIMEOUT_SEC = 900

#: Matches an ember table header: `[mcp_servers.ember]`, `[mcp_servers.ember.env]`,
#: tolerant of whitespace around dots and a trailing comment.
_EMBER_HEADER_RE = re.compile(
    r"^\[\s*mcp_servers\s*\.\s*ember(?:\s*\.\s*[A-Za-z0-9_-]+)*\s*\]\s*(?:#.*)?$"
)


def _validate_config_path(path: Path) -> None:
    """Raise ``ValueError`` unless ``path``'s final component is ``config.toml``.

    Parameters
    ----------
    path : Path
        The config file path to validate.

    Raises
    ------
    ValueError
        If ``path.name`` is not ``config.toml``.
    """
    if path.name != _ACCEPTED_BASENAME:
        raise ValueError(
            f"config path must end in {_ACCEPTED_BASENAME!r}; got {path.name!r}"
        )


def global_config_path() -> Path:
    """Return the user-global Codex CLI config path.

    Returns
    -------
    Path
        ``$CODEX_HOME/config.toml`` when ``CODEX_HOME`` is set and non-empty,
        else ``~/.codex/config.toml``.
    """
    codex_home = os.environ.get("CODEX_HOME", "")
    if codex_home:
        return Path(codex_home) / _ACCEPTED_BASENAME
    return Path.home() / ".codex" / _ACCEPTED_BASENAME


def project_config_path(root: Path) -> Path:
    """Return the project-local Codex CLI config path.

    Codex only loads this file for a trusted project (an interactive trust
    prompt, or a ``[projects."<abs>"] trust_level="trusted"`` entry in the
    global config) — callers should tell the user when writing here.

    Parameters
    ----------
    root : Path
        Project root directory.

    Returns
    -------
    Path
        ``<root>/.codex/config.toml``.
    """
    return root / ".codex" / _ACCEPTED_BASENAME


def _render_section(
    host: str,
    port: int,
    autostart: str,
    server_url: str | None,
    auth_header: str | None,
) -> str:
    """Render the `[mcp_servers.ember]` TOML block for the given settings.

    Parameters
    ----------
    host : str
        Model server host for ``EMBER_SERVER_URL`` when ``server_url`` is not
        given.
    port : int
        Model server port for ``EMBER_SERVER_URL`` when ``server_url`` is not
        given.
    autostart : str
        Value for ``EMBER_AUTOSTART`` (``"1"`` or ``"0"``); honored as given,
        not re-derived from ``server_url``.
    server_url : str | None
        A remote inference endpoint, replacing the local
        ``http://{host}:{port}`` URL.
    auth_header : str | None
        The header name a remote endpoint expects the credential on. Only
        rendered when both ``server_url`` and ``auth_header`` are given.

    Returns
    -------
    str
        The rendered block, ending in a single newline.
    """
    command, *args = mcp_command()
    env = {
        "EMBER_SERVER_URL": server_url or f"http://{host}:{port}",  # NOSONAR
        "EMBER_AUTOSTART": autostart,
    }
    if server_url and auth_header:
        env["EMBER_AUTH_HEADER"] = auth_header

    # json.dumps produces a TOML-valid basic string (JSON escaping is a subset of
    # TOML's basic-string escaping for the plain ASCII values we render here).
    env_inline = ", ".join(f"{key} = {json.dumps(value)}" for key, value in env.items())
    lines = [f"[mcp_servers.{_SERVER_KEY}]", f"command = {json.dumps(command)}"]
    if args:
        lines.append(f"args = {json.dumps(args)}")
    lines.extend(
        [
            f"env = {{ {env_inline} }}",
            f"env_vars = {json.dumps([_AUTH_ENV_VAR])}",
            "enabled = true",
            f"startup_timeout_sec = {_STARTUP_TIMEOUT_SEC}",
            f"tool_timeout_sec = {_TOOL_TIMEOUT_SEC}",
        ]
    )
    return "\n".join(lines) + "\n"


def _strip_ember_section(text: str) -> str:
    """Remove every ember table (and its nested sub-tables) from TOML text.

    Walks the text line by line: when an ember header is seen, that line and
    every following line are dropped until the next ``[``-starting header
    line (ember or not), which is kept along with the comment and blank lines
    directly above it (they describe that table, not ember's). This drops
    ``[mcp_servers.ember]`` and any nested ``[mcp_servers.ember.*]`` table in
    one pass while leaving every other line untouched.

    Parameters
    ----------
    text : str
        The TOML text to strip.

    Returns
    -------
    str
        ``text`` with every ember table removed.
    """
    out: list[str] = []
    pending: list[str] = []
    skipping = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("["):
            skipping = bool(_EMBER_HEADER_RE.match(stripped))
            if skipping:
                pending.clear()
                continue
            out.extend(pending)
            pending.clear()
        elif skipping:
            if not stripped or stripped.startswith("#"):
                pending.append(line)
            else:
                pending.clear()
            continue
        out.append(line)
    return "".join(out)


def _has_ember_section(text: str) -> bool:
    """Return whether ``text`` contains an ember table header.

    Parameters
    ----------
    text : str
        The TOML text to search.

    Returns
    -------
    bool
        ``True`` if any line matches the ember header pattern.
    """
    return any(_EMBER_HEADER_RE.match(line.strip()) for line in text.splitlines())


def _append_section(text: str, section: str) -> str:
    """Append ``section`` to ``text`` with one blank line of separation.

    Parameters
    ----------
    text : str
        Existing file text (ember section already stripped), may be empty.
    section : str
        The rendered ember block to append.

    Returns
    -------
    str
        The combined text, ending in exactly one trailing newline.
    """
    head = text.rstrip("\n")
    tail = section.rstrip("\n")
    return f"{head}\n\n{tail}\n" if head else f"{tail}\n"


def write(
    path: Path,
    host: str,
    port: int,
    autostart: str,
    server_url: str | None = None,
    auth_header: str | None = None,
) -> Path:
    """Merge the ``[mcp_servers.ember]`` section into a Codex config file.

    Preserves any other existing content in ``path`` — comments, unrelated
    tables, and key order — by splicing the ember section textually rather
    than re-serializing the whole file. Creates the file and its parent
    directories if they do not exist.

    Parameters
    ----------
    path : Path
        Config file to read and overwrite. Must end in ``config.toml``.
    host : str
        Model server host for ``EMBER_SERVER_URL`` when ``server_url`` is not
        given.
    port : int
        Model server port for ``EMBER_SERVER_URL`` when ``server_url`` is not
        given.
    autostart : str
        Value for ``EMBER_AUTOSTART`` (``"1"`` or ``"0"``).
    server_url : str | None, optional
        A remote inference endpoint to bootstrap the client against, in
        place of the local ``http://{host}:{port}`` URL.
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
        If ``path`` does not end in ``config.toml``, or if ``path`` already
        exists and is not valid TOML (the file is left untouched in that
        case).
    """
    _validate_config_path(path)
    existing_text = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing_text.strip():
        try:
            tomllib.loads(existing_text)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"existing {path} is invalid TOML: {exc}") from exc

    section = _render_section(host, port, autostart, server_url, auth_header)
    new_text = _append_section(_strip_ember_section(existing_text), section)
    try:
        tomllib.loads(new_text)  # validate the result before writing it out
    except tomllib.TOMLDecodeError as exc:
        # Only header-form ember tables are stripped; an inline or dotted-key
        # entry survives and collides with the appended section.
        raise ValueError(
            f"{path} declares mcp_servers.ember in a form ember cannot replace "
            f"(inline table or dotted keys); remove it and rerun: {exc}"
        ) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    # S2083: path passed _validate_config_path above; the basename guard sanitizes it
    tmp.write_text(new_text, encoding="utf-8")  # NOSONAR
    os.replace(tmp, path)
    return path


def remove(path: Path) -> bool:
    """Drop the ``[mcp_servers.ember]`` section; ``False`` if absent/unparseable.

    Parameters
    ----------
    path : Path
        Config file to modify. Must end in ``config.toml``.

    Returns
    -------
    bool
        ``True`` if the section was present and removed; ``False`` if the
        file is absent, is not valid TOML, has no ember section, or holds one
        ember cannot strip without breaking the file (left untouched).

    Raises
    ------
    ValueError
        If ``path`` does not end in ``config.toml``.
    """
    _validate_config_path(path)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return False
    if not _has_ember_section(text):
        return False

    new_text = _strip_ember_section(text)
    if new_text and not new_text.endswith("\n"):
        new_text += "\n"
    try:
        tomllib.loads(new_text)  # a hand-edited section can defeat the line splice
    except tomllib.TOMLDecodeError:
        return False
    tmp = path.with_suffix(".tmp")
    # S2083: path passed _validate_config_path above; the basename guard sanitizes it
    tmp.write_text(new_text, encoding="utf-8")  # NOSONAR
    os.replace(tmp, path)
    return True


def has_entry(path: Path) -> bool:
    """Return whether ``path`` registers ``mcp_servers.ember``, in any TOML form.

    Parameters
    ----------
    path : Path
        Config file to inspect. Must end in ``config.toml``.

    Returns
    -------
    bool
        ``False`` when the file is missing, malformed, or has no entry.

    Raises
    ------
    ValueError
        If ``path`` does not end in ``config.toml``.
    """
    _validate_config_path(path)
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    servers = parsed.get("mcp_servers")
    return isinstance(servers, dict) and _SERVER_KEY in servers
