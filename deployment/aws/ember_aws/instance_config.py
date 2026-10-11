"""InstanceConfig: the SSM config parameter read by the instance at every boot."""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

_S3_URI_RE = re.compile(r"^s3://[^/]+/.+[^/]$")


class InstanceConfig(BaseModel):
    """Configuration stored in SSM ``/ember/<name>/config`` (JSON).

    The instance reads this at every boot. ``generation`` increments on every
    deploy that changes anything; the converge unit skips install and sync when
    the stored generation matches the last applied one.

    Parameters
    ----------
    ember_version : str
        Pinned ``ember-advise`` version to install (``X.Y.Z``).
    model_s3_uri : str
        ``s3://<bucket>/models/<model>/<revision>`` — no trailing slash.
    max_request_length : int
        Per-request token cap from ``SizingEntry.request_cap``; must be > 0.
    idle_minutes : int
        Minutes of inactivity before the instance stops itself; 0 = off.
    generation : int
        Monotonically increasing counter; incremented on every config change.
    """

    ember_version: str
    model_s3_uri: str
    max_request_length: int
    idle_minutes: int
    generation: int

    @field_validator("model_s3_uri")
    @classmethod
    def _validate_s3_uri(cls, v: str) -> str:
        if not _S3_URI_RE.match(v):
            raise ValueError(
                f"model_s3_uri {v!r} must start with s3:// and end with"
                " /<revision> (no trailing slash)"
            )
        return v

    @field_validator("max_request_length")
    @classmethod
    def _validate_max_request_length(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"max_request_length must be > 0, got {v}")
        return v
