"""CachedModel and CachedFile: data models for the S3 model cache manifest."""

from __future__ import annotations

from pydantic import BaseModel


class CachedFile(BaseModel):
    """One file entry in a cached model manifest.

    Parameters
    ----------
    path : str
        Relative path within the model prefix (e.g. ``"config.json"``).
    size : int
        File size in bytes.
    sha256 : str
        Hex-encoded SHA-256 digest of the file contents.
    """

    path: str
    size: int
    sha256: str


class CachedModel(BaseModel):
    """A cached model's manifest record.

    Written as ``manifest.json`` under the model's S3 prefix, **last**,
    after all weight files have been uploaded.  A cached model is
    **complete** only when the manifest exists and every listed file
    matches its recorded size.

    Parameters
    ----------
    model : str
        Registry key (e.g. ``"flash"``).
    revision : str
        Hugging Face commit hash or tag.
    s3_uri : str
        Full S3 URI of the model prefix
        (e.g. ``"s3://<bucket>/models/flash/<revision>"``).
    total_bytes : int
        Sum of all file sizes in bytes.
    files : list[CachedFile]
        One entry per uploaded file, in upload order.
    """

    model: str
    revision: str
    s3_uri: str
    total_bytes: int
    files: list[CachedFile]
