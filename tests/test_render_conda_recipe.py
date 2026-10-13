"""Unit tests for scripts/render_conda_recipe.py (network-free)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_conda_recipe.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("render_conda_recipe", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


render_recipe = _load()

RECIPE = """\
context:
  version: "0.15.0"
  python_min: "3.12"

source:
  url: https://example.invalid/pkg-${{ version }}.tar.gz
  sha256: 91cf10abde277145d28e1c29e579b3dbfc21be563741438fe8fb63c20314b181
"""


def test_render_sets_only_the_context_version() -> None:
    out = render_recipe.render(RECIPE, "1.2.3", "a" * 64)
    assert 'version: "1.2.3"' in out
    assert 'python_min: "3.12"' in out


def test_render_sets_the_sdist_sha256() -> None:
    out = render_recipe.render(RECIPE, "1.2.3", "b" * 64)
    assert f"sha256: {'b' * 64}" in out
    assert "91cf10ab" not in out


def test_render_rejects_a_malformed_version() -> None:
    with pytest.raises(ValueError, match="version"):
        render_recipe.render(RECIPE, "1.2.3; rm -rf", "a" * 64)


def test_render_rejects_a_malformed_sha256() -> None:
    with pytest.raises(ValueError, match="sha256"):
        render_recipe.render(RECIPE, "1.2.3", "not-a-hash")
