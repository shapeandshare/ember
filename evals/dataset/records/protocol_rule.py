"""ProtocolRule: a protocol sentence and the dataset version it applies from."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProtocolRule(BaseModel):
    """A protocol rule recorded with the dataset version it first applies to.

    Parameters
    ----------
    text : str
        The rule as the report prints it.
    since : str
        The content hash (dataset version) the rule first applies to; a rule
        that changes is recorded again under the version the change starts
        with (FR-046).
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    since: str = Field(pattern=r"^[0-9a-f]{64}$")
