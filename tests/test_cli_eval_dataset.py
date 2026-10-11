"""CLI dispatch for the Phase 0 ``ember eval`` additions: ``eval dataset …``,
``eval run --resume``, ``eval snapshot --rebuild``. Lives apart from
``tests/test_cli.py`` so that module does not grow (Article X §10.3).
"""

from __future__ import annotations

import pytest
from ember import cli
from evals.dataset import card, check, hashes, lint, tiers


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
