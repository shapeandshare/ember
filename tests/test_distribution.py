"""Distribution contract: documented installs and manifests track the release."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
VERSION = PYPROJECT["project"]["version"]
SERVER_NAME = "io.github.shapeandshare/ember"
PLUGIN_ROOT = ROOT / "packages" / "claude-plugin"
CONDA = ROOT / "conda"

# A documented git install of ember over https or ssh, with an optional @ref.
GIT_INSTALL = re.compile(
    r"git\+(?:https://github\.com/|ssh://git@github\.com/)shapeandshare/ember"
    r"(?P<ref>@[^\"`\s)]*)?"
)
INSTALL_DOCS = ("README.md", "site/index.md")
VERSIONED_MANIFESTS = (
    "server.json",
    "packages/claude-plugin/.claude-plugin/plugin.json",
)


def _version_files() -> dict[str, str]:
    entries = PYPROJECT["tool"]["commitizen"]["version_files"]
    return dict(entry.split(":", 1) for entry in entries)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", INSTALL_DOCS)
def test_git_installs_pin_the_current_release_tag(name: str) -> None:
    text = (ROOT / name).read_text(encoding="utf-8")
    refs = [match.group("ref") for match in GIT_INSTALL.finditer(text)]
    assert refs, f"{name} documents no git install"
    assert refs == [f"@v{VERSION}"] * len(refs)


@pytest.mark.parametrize("name", INSTALL_DOCS)
def test_version_bumps_rewrite_every_pinned_install(name: str) -> None:
    pattern = re.compile(_version_files()[name])
    lines = (ROOT / name).read_text(encoding="utf-8").splitlines()
    pinned = [line for line in lines if GIT_INSTALL.search(line)]
    assert pinned
    assert all(pattern.search(line) for line in pinned)


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


def test_readme_carries_the_registry_ownership_marker() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"<!-- mcp-name: {SERVER_NAME} -->" in readme


def test_marketplace_lists_the_ember_plugin() -> None:
    marketplace = _json(ROOT / ".claude-plugin" / "marketplace.json")
    (entry,) = marketplace["plugins"]
    assert marketplace["name"] == "ember"
    assert marketplace["owner"]["name"]
    assert entry["name"] == "ember"
    assert (ROOT / entry["source"]).resolve() == PLUGIN_ROOT


def test_plugin_launches_the_installed_mcp_server() -> None:
    plugin = _json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")
    assert plugin["name"] == "ember"
    assert plugin["mcpServers"] == {"ember": {"command": "ember-mcp"}}


def test_plugin_skill_mirrors_the_agent_kit_skill() -> None:
    kit = ROOT / "ember" / "agent_kit" / "ember-advise" / "SKILL.md"
    mirror = PLUGIN_ROOT / "skills" / "ember-advise" / "SKILL.md"
    assert mirror.read_bytes() == kit.read_bytes(), f"copy {kit} to {mirror}"


def test_registry_launch_command_runs_the_ember_cli() -> None:
    (package,) = _json(ROOT / "server.json")["packages"]
    scripts = PYPROJECT["project"]["scripts"]
    assert scripts.get(package["identifier"]) == "ember.cli:main"


def test_conda_recipe_is_a_valid_submission() -> None:
    recipe = _yaml(CONDA / "recipe.yaml")
    assert recipe["package"]["name"] == "ember-advise"
    assert re.fullmatch(r"\d+\.\d+\.\d+", recipe["context"]["version"])
    assert recipe["build"]["skip"] == ["win"]
    entry_points = recipe["build"]["python"]["entry_points"]
    names = sorted(entry.split(" = ", 1)[0] for entry in entry_points)
    assert names == ["ember", "ember-advise", "ember-mcp", "gut"]


def test_conda_recipe_run_dependencies_mirror_the_release() -> None:
    run = "\n".join(_yaml(CONDA / "recipe.yaml")["requirements"]["run"])
    pins = (
        "pytorch >=2.12,<2.14",
        "torchvision >=0.27,<0.29",
        "transformers >=5.18,<6",
        "safetensors >=0.8,<1",
        "huggingface_hub >=1.32,<2",
        "accelerate >=1.15,<2",
        "pillow >=12,<13",
        "fastapi >=0.142,<1",
        "uvicorn-standard >=0.54,<1",
        "pydantic >=2.13,<3",
        "mcp >=2.3,<3",
        "httpx >=0.28,<1",
        "prometheus_client >=0.21,<1",
        "boto3 >=1.40,<2",
    )
    missing = [pin for pin in pins if pin not in run]
    assert not missing, f"recipe is missing pins: {missing}"


def test_conda_recipe_about_metadata_matches_the_project() -> None:
    about = _yaml(CONDA / "recipe.yaml")["about"]
    assert about["license"] == "MIT"
    assert about["license_file"] == "LICENSE"
    assert about["homepage"] == "https://shapeandshare.github.io/ember/"
    assert about["repository"] == "https://github.com/shapeandshare/ember"


def test_conda_lock_environment_excludes_ember_itself() -> None:
    spec = _yaml(CONDA / "lock-environment.yml")
    assert spec["channels"] == ["conda-forge"]
    assert set(spec["platforms"]) == {"osx-arm64", "linux-64"}
    assert "ember-advise" not in "\n".join(spec["dependencies"])


def test_conda_lock_covers_both_platforms_with_hashes() -> None:
    lock = _yaml(CONDA / "ember-deps.conda-lock.yml")
    platforms = {"osx-arm64", "linux-64"}
    assert set(lock["metadata"]["platforms"]) == platforms
    assert {package["platform"] for package in lock["package"]} == platforms
    content_hash = lock["metadata"]["content_hash"]
    for platform in sorted(platforms):
        assert re.fullmatch(r"[0-9a-f]{64}", content_hash[platform])


def test_release_dispatches_the_conda_publish() -> None:
    # A bot-created release does not fire conda-package.yml's `release` trigger (GitHub
    # suppresses GITHUB_TOKEN events), so release-ember dispatches it instead, and the
    # dispatch is what turns the upload on.
    release = _yaml(ROOT / ".github" / "workflows" / "release-ember.yml")
    conda = _yaml(ROOT / ".github" / "workflows" / "conda-package.yml")

    runs = [
        step["run"]
        for step in release["jobs"]["publish-conda"]["steps"]
        if "run" in step
    ]
    assert any("gh workflow run conda-package.yml" in run for run in runs)
    assert any("publish=true" in run for run in runs)

    assert "inputs.publish" in conda["jobs"]["publish"]["if"]


def test_conda_smoke_prefers_conda_forge_with_the_interim_fallback() -> None:
    # Order matters: conda-forge must come first so it wins once the feedstock
    # publishes, with joshburt only supplying the package until then — which is
    # what lets the smoke run today and self-transition at onboarding.
    testing_mk = (ROOT / "shared" / "testing.mk").read_text(encoding="utf-8")
    (install,) = [line for line in testing_mk.splitlines() if "ember-advise==" in line]
    assert install.index("-c conda-forge") < install.index("-c joshburt")
