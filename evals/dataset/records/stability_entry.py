"""StabilityEntry: one item's blinded re-label in a stability round."""

from __future__ import annotations

from pydantic import BaseModel


class StabilityEntry(BaseModel):
    """One item's re-label record inside a stability round.

    Annotation-only: nothing here enters the dataset content hash.

    Parameters
    ----------
    id : str
        The re-labelled item's id.
    category : str
        The recipe the item belongs to (e.g. ``"change_risk"``).
    question : str
        The question within the recipe (e.g. ``"risk"``).
    original : int
        The gold level the item carried when the sheet was emitted.
    relabel : int
        The blinded re-label level.
    agrees : bool
        Whether ``relabel == original``; computed by the tool, never provided.
    labelled_on : str
        ISO date the re-label was made.
    """

    id: str
    category: str
    question: str
    original: int
    relabel: int
    agrees: bool
    labelled_on: str
