"""Distribution contract: documented installs and manifests track the release."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
VERSION = PYPROJECT["project"]["version"]
SERVER_NAME = "io.github.shapeandshare/ember"
VERSIONED_MANIFESTS = ("server.json",)


def _version_files() -> dict[str, str]:
    entries = PYPROJECT["tool"]["commitizen"]["version_files"]
    return dict(entry.split(":", 1) for entry in entries)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", VERSIONED_MANIFESTS)
def test_version_bumps_rewrite_every_manifest_version(name: str) -> None:
    pattern = re.compile(_version_files()[name])
    lines = [
        line
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
        if '"version"' in line
    ]
    assert lines
    assert all(pattern.search(line) and f'"{VERSION}"' in line for line in lines)


def test_server_json_describes_the_published_pypi_package() -> None:
    server = _json(ROOT / "server.json")
    (package,) = server["packages"]
    assert server["name"] == SERVER_NAME
    assert 1 <= len(server["description"]) <= 100
    assert package["registryType"] == "pypi"
    assert package["identifier"] == PYPROJECT["project"]["name"]
    assert package["transport"] == {"type": "stdio"}
    assert [arg["value"] for arg in package["packageArguments"]] == ["mcp"]


def test_registry_launch_command_runs_the_ember_cli() -> None:
    (package,) = _json(ROOT / "server.json")["packages"]
    scripts = PYPROJECT["project"]["scripts"]
    assert scripts.get(package["identifier"]) == "ember.cli:main"
