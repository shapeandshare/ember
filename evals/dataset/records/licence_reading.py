"""LicenceReading: a data source's licence as read on a given date."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from .licence_class import LicenceClass


class LicenceReading(BaseModel):
    """What the licence page said, where, when, and how it bears on redistribution.

    Parameters
    ----------
    reading : str
        The licence as read (for example ``CC BY 4.0``).
    spdx : str | None
        The SPDX identifier when one applies.
    read_at : str
        The URL the licence was read at.
    read_on : date
        When it was read.
    class_ : LicenceClass
        How it bears on redistribution here; serialised as ``class``.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    reading: str = Field(min_length=1)
    spdx: str | None = None
    read_at: str = Field(min_length=1, pattern=r"^https?://")
    read_on: date
    class_: LicenceClass = Field(alias="class")
