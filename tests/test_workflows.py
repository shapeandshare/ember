"""Every GitHub Actions workflow parses as YAML.

GitHub rejects a workflow whose YAML is invalid, but it only surfaces the error in
the Actions tab — an invalid workflow can merge unnoticed. A common trap is a plain
(`name: …`) scalar holding a ``": "`` (colon-space), which ends the scalar early. This
guards against it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def test_workflows_exist() -> None:
    assert WORKFLOWS


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_parses(workflow: Path) -> None:
    yaml.safe_load(workflow.read_text(encoding="utf-8"))
