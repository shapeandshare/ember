"""MineError: a mining precondition failed; the message names the missing thing."""

from __future__ import annotations


class MineError(RuntimeError):
    """The miner refused: a required precondition (the grant) is absent."""
