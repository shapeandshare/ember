"""SnapshotRef: the exact upstream snapshot an import was taken from."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SnapshotRef(BaseModel):
    """A retrieved snapshot's version and content hash.

    Parameters
    ----------
    version : str
        The upstream version, commit, or release tag.
    sha256 : str
        SHA-256 of the retrieved archive.
    retrieved_on : date
        When it was retrieved.
    """

    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_on: date
