"""ExampleSecret: a vendor-documented example credential the guard allow-lists."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ExampleSecret(BaseModel):
    """One documented example value such as AWS's ``AKIAIOSFODNN7EXAMPLE``.

    Parameters
    ----------
    value : str
        The exact string that may appear in an item's state.
    vendor : str
        Who documents it.
    url : str
        Where it is documented.
    read_on : date
        When the page was read.
    """

    model_config = ConfigDict(frozen=True)

    value: str = Field(min_length=1)
    vendor: str = Field(min_length=1)
    url: str = Field(min_length=1, pattern=r"^https?://")
    read_on: date
