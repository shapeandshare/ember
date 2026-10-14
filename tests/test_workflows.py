"""Every GitHub Actions workflow parses, and uses only allow-listed actions.

GitHub rejects a workflow whose YAML is invalid, and a step using an action outside
the repository's Actions allow-list makes the whole workflow fail to start
(``startup_failure``). Both only surface in the Actions tab, so an invalid or blocked
workflow can merge unnoticed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

GITHUB_OWNED_PREFIX = "actions/"
# Mirrors Settings -> Actions -> "Allow select actions". A workflow using anything
# outside GitHub-owned actions plus these publishers will not start; keep this in
# step with the setting.
ALLOWED_THIRD_PARTY = (
    "astral-sh/setup-uv",
    "zizmorcore/zizmor-action",
    "ruby/setup-ruby",
    "SonarSource/sonarqube-scan-action",
)


def _steps(workflow: Path) -> list[dict[str, object]]:
    document = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
    steps: list[dict[str, object]] = []
    for job in (document.get("jobs") or {}).values():
        steps.extend(job.get("steps") or [])
    return steps


def test_workflows_exist() -> None:
    assert WORKFLOWS


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_parses(workflow: Path) -> None:
    yaml.safe_load(workflow.read_text(encoding="utf-8"))


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_actions_are_allow_listed(workflow: Path) -> None:
    blocked = [
        uses
        for step in _steps(workflow)
        if (uses := step.get("uses"))
        and not str(uses).split("@", 1)[0].startswith(GITHUB_OWNED_PREFIX)
        and str(uses).split("@", 1)[0] not in ALLOWED_THIRD_PARTY
    ]
    assert not blocked, (
        f"{workflow.name} uses actions the repository allow-list blocks, so the "
        f"workflow would fail to start: {blocked}"
    )
