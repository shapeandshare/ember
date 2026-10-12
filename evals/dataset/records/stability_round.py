"""StabilityRound: one committed stability round over scoped recipes."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from .stability_entry import StabilityEntry


class StabilityRound(BaseModel):
    """A committed re-label round: the owner of ``evals/dataset/stability/<id>.json``.

    Parameters
    ----------
    round_id : str
        The round identifier (e.g. ``"2026-10-11-risk-effort"``).
    cooling_off : str
        The declared cooling-off window (e.g. ``"7d"``), stated in the report.
    method : str
        How blinding was ensured (e.g. ``"original labels withheld"``).
    labelled_on : str
        ISO date the round completed.
    entries : list[StabilityEntry]
        One per re-labelled item; no item appears twice.
    """

    round_id: str
    cooling_off: str
    method: str
    labelled_on: str
    entries: list[StabilityEntry]

    @field_validator("entries")
    @classmethod
    def _unique_ids(cls, value: list[StabilityEntry]) -> list[StabilityEntry]:
        seen: set[str] = set()
        for entry in value:
            if entry.id in seen:
                raise ValueError(f"item {entry.id!r} appears twice in one round")
            seen.add(entry.id)
        return value
