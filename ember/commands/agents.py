"""Agent onboarding and init subcommand handlers: init, agents install/show, uninstall."""  # noqa: E501

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .. import models as models_mod
from ..agent_kit import api as agent_kit
from ..cfg import paths
from ..codex import codex_config
from ..kilocode import kilocode_config
from ..opencode import opencode_config, opencode_plugin
from ..serving import process
from .endpoint import host_port
from .registration import codex_trust_note


def cmd_init(args: argparse.Namespace) -> int:
    """Register the MCP server with opencode, Kilo Code, and/or Codex CLI.

    This is ``ember init``. When ``args.server_url`` is given, bootstraps the
    client against that remote endpoint instead of a local loopback server:
    ``EMBER_AUTOSTART`` is forced off (there is nothing local to autostart)
    and, if ``args.auth_header`` is set, its name is recorded. The credential
    itself is never written to a config file — export ``EMBER_AUTH_TOKEN`` in
    the shell that launches the agent instead.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags plus ``args.global_``,
        ``args.opencode``, ``args.kilocode``, ``args.codex``,
        ``args.no_autostart``, ``args.server_url``, and ``args.auth_header``.

    Returns
    -------
    int
        Always ``0``.

    Raises
    ------
    RuntimeError
        If an existing config file cannot be merged into without losing its
        content (that file is left untouched), or a file cannot be written.
    """
    try:
        return _register(args)
    except (OSError, ValueError) as exc:
        raise RuntimeError(str(exc)) from exc


def _register(args: argparse.Namespace) -> int:
    """Write every registration ``cmd_init`` was asked for.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed ``ember init`` arguments.

    Returns
    -------
    int
        Always ``0``.
    """
    host, port = host_port(args)
    server_url = getattr(args, "server_url", None)
    auth_header = getattr(args, "auth_header", None)
    autostart = "0" if (args.no_autostart or server_url) else "1"
    scope = "global" if args.global_ else "project"
    target = (
        opencode_config.global_config_path()
        if args.global_
        else opencode_config.project_config_path(Path.cwd())
    )
    command = opencode_config.mcp_command()
    written = opencode_config.write(
        target, host, port, autostart, server_url, auth_header
    )
    print(f"wrote {written}")
    if server_url:
        print(f"  remote endpoint: {server_url}")
        print("  export EMBER_AUTH_TOKEN in your shell if the endpoint requires one")
    if args.opencode:
        effective_url = server_url or f"http://{host}:{port}"  # NOSONAR - local default
        plugin = opencode_plugin.install(
            command,
            effective_url,
            scope=scope,
            autostart=autostart,
            auth_header=auth_header,
        )
        print(f"installed opencode plugin: {plugin}")
        skill = agent_kit.install_skill("opencode", scope, Path.cwd())
        print(f"installed {agent_kit.SKILL_NAME} skill: {skill}")
    if args.kilocode:
        kilo_target = (
            kilocode_config.global_config_path()
            if args.global_
            else kilocode_config.project_config_path(Path.cwd())
        )
        kilo_written = kilocode_config.write(
            kilo_target, host, port, autostart, server_url, auth_header
        )
        print(f"wrote {kilo_written}")
        skill = agent_kit.install_skill("kilocode", scope, Path.cwd())
        print(f"installed {agent_kit.SKILL_NAME} skill: {skill}")
    if args.codex:
        _register_codex(args.global_, host, port, autostart, server_url, auth_header)
    print(f"  command: {command}")
    print("restart opencode/kilo/codex to pick up changes")
    return 0


def _register_codex(
    global_: bool,
    host: str,
    port: int,
    autostart: str,
    server_url: str | None,
    auth_header: str | None,
) -> None:
    """Write the Codex CLI entry and skill, and say whether Codex will load it.

    Parameters
    ----------
    global_ : bool
        Register in the user-global Codex config instead of this project's.
    host : str
        Model server host for a local endpoint.
    port : int
        Model server port for a local endpoint.
    autostart : str
        Value for ``EMBER_AUTOSTART``.
    server_url : str | None
        A remote inference endpoint, if any.
    auth_header : str | None
        The header name a remote endpoint expects the credential on.
    """
    target = (
        codex_config.global_config_path()
        if global_
        else codex_config.project_config_path(Path.cwd())
    )
    written = codex_config.write(target, host, port, autostart, server_url, auth_header)
    print(f"wrote {written}")
    scope = "global" if global_ else "project"
    skill = agent_kit.install_skill("codex", scope, Path.cwd())
    print(f"installed {agent_kit.SKILL_NAME} skill: {skill}")
    if global_:
        return
    note = codex_trust_note(Path.cwd())
    trusted = "  codex: this project is trusted; Codex will load it"
    print(f"  note: .codex/config.toml is {note}" if note else trusted)


def cmd_agents_install(args: argparse.Namespace) -> int:
    """Install the onboarding skill for an agent (``ember agents install``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.agent`` and ``args.global_``.

    Returns
    -------
    int
        Always ``0``.
    """
    scope = "global" if args.global_ else "project"
    path = agent_kit.install_skill(args.agent, scope, Path.cwd())
    print(f"installed {agent_kit.SKILL_NAME} skill for {args.agent}: {path}")
    return 0


def cmd_agents_show(args: argparse.Namespace) -> int:
    """Print part of the onboarding kit (``ember agents show``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.what`` (``"instructions"``,
        ``"skill"``, or ``"snippet"``).

    Returns
    -------
    int
        Always ``0``.
    """
    text = {
        "instructions": agent_kit.instructions,
        "skill": agent_kit.skill,
        "snippet": agent_kit.snippet,
    }[args.what]()
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Stop the server and remove global installs (``ember uninstall``).

    Removes the global opencode, Kilo Code, and Codex CLI MCP entries, the
    global opencode plugin, and every agent's global skill install.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``args.purge_models``.

    Returns
    -------
    int
        Always ``0``.
    """
    if process.stop():
        print("stopped the model server")
    if args.purge_models:
        for row in models_mod.list_models():
            if row["cached"]:
                print(models_mod.remove(row["name"]))

    global_plugin = (
        opencode_plugin.plugin_dir("global") / opencode_plugin.PLUGIN_FILENAME
    )
    if global_plugin.exists():
        global_plugin.unlink()
        print(f"removed {global_plugin}")
    for agent in agent_kit.AGENTS:
        skill_dir = agent_kit.skill_path(agent, "global").parent
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
            print(f"removed {skill_dir}")
    if opencode_config.remove(opencode_config.global_config_path()):
        print(f"removed mcp.ember from {opencode_config.global_config_path()}")
    if kilocode_config.remove(kilocode_config.global_config_path()):
        print(f"removed mcp.ember from {kilocode_config.global_config_path()}")
    if codex_config.remove(codex_config.global_config_path()):
        print(f"removed mcp_servers.ember from {codex_config.global_config_path()}")
    for directory in {paths.state_dir(), paths.config_dir()}:
        shutil.rmtree(directory, ignore_errors=True)
        print(f"removed {directory}")

    print(
        "project installs are left in place: in each initialized project, remove the "
        "`mcp.ember`/`mcp_servers.ember` entry from opencode.json, kilo.json, "
        "and/or .codex/config.toml, "
        f".opencode/plugins/{opencode_plugin.PLUGIN_FILENAME}, "
        f"and any {agent_kit.SKILL_NAME} skill directories"
    )
    print("then run: uv tool uninstall ember-advise")
    return 0
