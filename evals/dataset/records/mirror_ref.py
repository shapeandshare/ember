"""MirrorRef: the project's own copy of an upstream snapshot."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MirrorRef(BaseModel):
    """Where the project mirrors a snapshot outside the repository.

    Parameters
    ----------
    location : str
        A release asset or object-storage address.
    sha256 : str
        SHA-256 of the mirrored archive; must equal the snapshot's.
    public : bool
        Whether the mirror is itself a redistribution (it then carries the
        row's attribution notice).
    """

    model_config = ConfigDict(frozen=True)

    location: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public: bool
