"""Agent onboarding and init subcommand handlers: init, agents install/show, uninstall."""  # noqa: E501

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .. import models as models_mod
from ..agent_kit import api as agent_kit
from ..cfg import paths
from ..opencode import opencode_config, opencode_plugin
from ..serving import process
from .endpoint import host_port


def cmd_init(args: argparse.Namespace) -> int:
    """Register the MCP server with opencode (``ember init``).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses the server flags plus ``args.global_``,
        ``args.opencode``, and ``args.no_autostart``.

    Returns
    -------
    int
        Always ``0``.
    """
    host, port = host_port(args)
    autostart = "0" if args.no_autostart else "1"
    scope = "global" if args.global_ else "project"
    target = (
        opencode_config.global_config_path()
        if args.global_
        else opencode_config.project_config_path(Path.cwd())
    )
    command = opencode_config.mcp_command()
    print(f"wrote {opencode_config.write(target, host, port, autostart)}")
    if args.opencode:
        local_url = f"http://{host}:{port}"  # NOSONAR - loopback server only
        plugin = opencode_plugin.install(command, local_url, scope=scope)
        print(f"installed opencode plugin: {plugin}")
        skill = agent_kit.install_skill("opencode", scope, Path.cwd())
        print(f"installed {agent_kit.SKILL_NAME} skill: {skill}")
    print(f"  command: {command}")
    print("restart opencode to pick up changes")
    return 0


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
    for directory in {paths.state_dir(), paths.config_dir()}:
        shutil.rmtree(directory, ignore_errors=True)
        print(f"removed {directory}")

    print(
        "project installs are left in place: in each initialized project, remove the "
        "`mcp.ember` entry from opencode.json, "
        f".opencode/plugins/{opencode_plugin.PLUGIN_FILENAME}, "
        f"and any {agent_kit.SKILL_NAME} skill directories"
    )
    print("then run: uv tool uninstall gut")
    return 0
