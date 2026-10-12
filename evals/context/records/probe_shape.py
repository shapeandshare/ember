"""ProbeShape: the long-context figures a leaderboard row publishes."""

from __future__ import annotations

from pydantic import BaseModel

from .depth import Depth


class ProbeShape(BaseModel):
    """A row's long-context shape, taken from a matching probe run.

    Parameters
    ----------
    request_cap : int | None
        The longest passing request length (``ModelVerdict.cap``).
    first_drop_length : int | None
        The first failing length (``ModelVerdict.first_failure_length``).
    worst_depth : Depth | None
        The failing depth, when the failure is depth-specific.
    """

    request_cap: int | None
    first_drop_length: int | None
    worst_depth: Depth | None
