"""CLI dispatch for the Phase 0 ``ember eval`` additions: ``eval dataset …``,
``eval run --resume``, ``eval snapshot --rebuild``. Lives apart from
``tests/test_cli.py`` so that module does not grow (Article X §10.3).
"""

from __future__ import annotations

import pytest
from ember import cli
from evals.dataset import card, check, hashes, kinds, lint, stability, tiers


@pytest.mark.parametrize(
    ("argv", "module", "expected"),
    [
        (["lint", "--enforce-all", "--json"], lint, ["--enforce-all", "--json"]),
        (["lint", "--dataset", "x.jsonl"], lint, ["--dataset", "x.jsonl"]),
        (["card", "--check"], card, ["--check"]),
        (["card", "--dataset", "x.jsonl"], card, ["--dataset", "x.jsonl"]),
        (["hash", "--json"], hashes, ["--json"]),
        (["check", "--dataset", "x.jsonl"], check, ["--dataset", "x.jsonl"]),
        (
            ["tier", "--from", "bench", "--dataset", "x.jsonl"],
            tiers,
            ["--from", "bench", "--dataset", "x.jsonl"],
        ),
        (["stability", "--emit"], stability, ["--emit"]),
        (
            ["stability", "--ingest", "sheet.json", "--rounds-dir", "rounds"],
            stability,
            ["--ingest", "sheet.json", "--rounds-dir", "rounds"],
        ),
        (["kind", "--json"], kinds, ["--json"]),
    ],
)
def test_eval_dataset_dispatches_to_the_module_main(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    module: object,
    expected: list[str],
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(module, "main", lambda a: calls.append(list(a)) or 0)
    assert cli.main(["eval", "dataset", *argv]) == 0
    assert calls == [expected]


def test_eval_dataset_without_a_subcommand_is_an_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli.main(["eval", "dataset"])


def test_eval_context_device_flag_is_passed_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals.context import run_context

    received: list[list[str]] = []

    def fake_main(argv: list[str]) -> int:
        received.append(list(argv))
        return 0

    monkeypatch.setattr(run_context, "main", fake_main)
    assert cli.main(["eval", "context", "--device", "cuda"]) == 0
    assert received == [["--device", "cuda"]]


def test_eval_run_resume_and_snapshot_rebuild_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals.eval import run_evals, snapshot_evals

    seen: dict[str, object] = {}

    def fake_run(server: str, **kwargs: object) -> int:
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(run_evals, "run_evals", fake_run)
    assert cli.main(["eval", "run", "--resume", "clef-flash_x"]) == 0
    assert seen["resume"] == "clef-flash_x"

    calls: list[list[str]] = []
    monkeypatch.setattr(
        snapshot_evals, "main", lambda argv: calls.append(list(argv)) or 0
    )
    assert cli.main(["eval", "snapshot", "--rebuild", "clef-flash_x"]) == 0
    assert calls == [["--rebuild", "clef-flash_x"]]


def test_eval_run_forwards_the_deployment_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The deployment label reaches run_evals from the flag and the environment.

    Without this, every CLI-driven benchmark records the generic derived label,
    so different remote deployments collide on one leaderboard row.
    """
    from evals.eval import run_evals

    seen: dict[str, object] = {}

    def fake_run(server: str, **kwargs: object) -> int:
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(run_evals, "run_evals", fake_run)
    assert cli.main(["eval", "run", "--deployment-label", "Remote hosted - X"]) == 0
    assert seen["deployment_label"] == "Remote hosted - X"

    seen.clear()
    monkeypatch.setenv("EMBER_DEPLOYMENT_LABEL", "Remote hosted - Y")
    assert cli.main(["eval", "run"]) == 0
    assert seen["deployment_label"] == "Remote hosted - Y"


def test_eval_capture_dispatches_through_the_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ember eval capture import ...` forwards its args unchanged."""
    from evals.dataset import capture

    received: list[list[str]] = []
    monkeypatch.setattr(capture, "main", lambda argv: received.append(list(argv)) or 0)
    assert cli.main(["eval", "capture", "import", "t.json", "r.json"]) == 0
    assert received == [["import", "t.json", "r.json"]]
