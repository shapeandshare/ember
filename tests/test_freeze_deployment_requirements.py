"""Unit tests for scripts/freeze_deployment_requirements.py.

``uv export --no-emit-project`` deliberately omits ember-advise's own project
package from ``deployment/requirements.txt`` (see
``vault/decisions/2026-10-08-outerbounds-deployment-and-cuda-support.md``).
Outerbounds' Fast Bakery only ``pip install``s what is listed in that file and
does not implicitly install the packaged source tree, so without an explicit
``ember-advise==<version>`` line the deployed container never gets the
``[project.scripts]`` entry points (``ember``, ``gut``, ``ember-mcp``) — see
``ember serve`` failing with ``ember: command not found``. This script must
re-add that line, pinned to the version in ``pyproject.toml``, every time it
resolves markers.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "freeze_deployment_requirements",
    ROOT / "scripts" / "freeze_deployment_requirements.py",
)
assert _SPEC is not None
assert _SPEC.loader is not None
freeze = importlib.util.module_from_spec(_SPEC)
sys.modules["freeze_deployment_requirements"] = freeze
_SPEC.loader.exec_module(freeze)


def test_main_adds_ember_advise_pin_when_missing(tmp_path, monkeypatch) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "accelerate==1.15.0\n"
        "    # via ember-advise\n"
        "boto3==1.43.109 ; sys_platform == 'linux'\n"
        "    # via ember-advise\n"
    )
    monkeypatch.setattr(freeze, "REQUIREMENTS_PATH", requirements)
    monkeypatch.setattr(freeze, "_PROJECT_VERSION", "9.9.9")

    exit_code = freeze.main()

    assert exit_code == 0
    lines = requirements.read_text().splitlines()
    assert "ember-advise==9.9.9" in lines


def test_main_is_idempotent_when_pin_already_present(tmp_path, monkeypatch) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("accelerate==1.15.0\n    # via ember-advise\n")
    monkeypatch.setattr(freeze, "REQUIREMENTS_PATH", requirements)
    monkeypatch.setattr(freeze, "_PROJECT_VERSION", "9.9.9")

    freeze.main()
    first_pass = requirements.read_text()
    freeze.main()
    second_pass = requirements.read_text()

    assert first_pass == second_pass
    assert first_pass.count("ember-advise==9.9.9") == 1


def test_main_errors_when_requirements_file_missing(tmp_path, monkeypatch) -> None:
    missing = tmp_path / "does-not-exist.txt"
    monkeypatch.setattr(freeze, "REQUIREMENTS_PATH", missing)

    exit_code = freeze.main()

    assert exit_code != 0
