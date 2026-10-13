"""CLI wiring for ``ember eval mine`` (specs/007 T014)."""

from __future__ import annotations

import pytest
from ember import cli


def test_eval_mine_rejects_an_unknown_recipe() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["eval", "mine", "--recipe", "nope"])
    assert excinfo.value.code == 2


def test_eval_mine_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["eval", "mine", "--help"])
    assert excinfo.value.code == 0


def test_eval_mine_reports_a_missing_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "evals.dataset.mined.mine", None)
    assert cli.main(["eval", "mine"]) == 1
