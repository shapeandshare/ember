"""CLI wiring for the ``replace`` subcommand."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from ember_aws.__main__ import build


def _factory(lc: MagicMock) -> Any:
    def factory(
        clients: Any, tailscale: Any, name: Any = None
    ) -> tuple[Any, Any, Any, Any, Any]:
        return MagicMock(), MagicMock(), MagicMock(), lc, MagicMock()

    return factory


def test_replace_calls_lifecycle_replace_and_exits_0() -> None:
    lc = MagicMock()
    code = build(["replace", "--name", "team-a1"], _factory(lc))
    assert code == 0
    deployment = lc.replace.call_args.args[0]
    assert deployment.name == "team-a1"


def test_replace_exits_2_on_failure() -> None:
    lc = MagicMock()
    lc.replace.side_effect = RuntimeError("boom")
    assert build(["replace", "--name", "default"], _factory(lc)) == 2
