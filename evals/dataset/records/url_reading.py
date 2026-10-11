"""UrlReading: a URL and the date it was read."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class UrlReading(BaseModel):
    """One URL of a data source and when it was last read.

    Parameters
    ----------
    url : str
        The address.
    read_on : date
        When it was read.
    """

    model_config = ConfigDict(frozen=True)

    url: str = Field(min_length=1, pattern=r"^https?://")
    read_on: date
