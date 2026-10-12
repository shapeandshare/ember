"""Startup-time resolution of an operator-supplied S3 model location.

Constitution Article V ("Model Loading"): ember supports any model that can
run under its loader contract. When ember runs as a deployed app on a hosting
platform (e.g. Outerbounds) that supplies the model's location as an
``s3://bucket/prefix`` URI at start time rather than a ``REGISTRY`` key
(the usual convention for a platform-deployed model),
``EMBER_MODEL_S3_URI`` names that location directly — no ``REGISTRY`` entry,
revision, or hash is required.

This module is read once, at process startup (``ember.serving.process.start``
and ``ember.serving.server``'s lifespan), before the server begins serving —
the same fail-fast-before-ready timing Article XIV already requires for a
missing model, not a lazy per-request ``config.resolve()`` read.

Completion marker
-----------------
A download is only considered complete when ``COMPLETION_MARKER`` exists
inside the cache directory.  The marker is written atomically (via a sibling
``.tmp`` file + ``os.replace``) after every successful download.

A non-empty directory that lacks the marker is treated as **partial** and
re-downloaded in full.  This closes the R4 bug where a partially downloaded
cache was silently accepted as complete because the old guard only checked
``any(model_dir.iterdir())``.

Existing complete caches that pre-date the marker (i.e. non-empty directories
without it) are also treated as incomplete and re-downloaded.  This is the
safest behaviour: a redundant re-download is far less harmful than serving a
corrupt model.  The docstring of :func:`resolve` explains this choice.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ..cfg import config, paths, s3

_URI_ENV = "EMBER_MODEL_S3_URI"

COMPLETION_MARKER = "_download_complete"


@dataclass(frozen=True)
class HostedModelSource:
    """A resolved, operator-supplied S3 model location.

    Attributes
    ----------
    uri : str
        The full ``s3://bucket/prefix`` URI this was resolved from.
    model_dir : Path
        The local directory the model's files were downloaded into (or
        already present in, from a prior resolution of the same URI).
    """

    uri: str
    model_dir: Path


def _parse_uri(uri: str) -> tuple[str, str]:
    """Split an ``s3://bucket/prefix`` URI into its bucket and prefix.

    Parameters
    ----------
    uri : str
        The URI to parse.

    Returns
    -------
    tuple[str, str]
        ``(bucket, prefix)``.

    Raises
    ------
    RuntimeError
        If ``uri`` is not a well-formed ``s3://bucket/prefix`` URI, or has no
        prefix (a bucket root is never a valid single-model location).
    """
    parsed = urlparse(uri)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    if parsed.scheme != "s3" or not bucket or not prefix:
        raise RuntimeError(
            f"{_URI_ENV}={uri!r} is not a well-formed s3://bucket/prefix URI "
            "(a bucket root with no prefix is not a valid single-model location)."
        )
    return bucket, prefix


def _is_complete(model_dir: Path) -> bool:
    """Return ``True`` when ``model_dir`` holds a completed download.

    Parameters
    ----------
    model_dir : Path
        The local cache directory to inspect.

    Returns
    -------
    bool
        ``True`` only when the directory exists **and** contains
        ``COMPLETION_MARKER``.  A non-empty directory without the marker is
        treated as partial (the R4 bug: old code accepted any non-empty dir).
    """
    return model_dir.is_dir() and (model_dir / COMPLETION_MARKER).exists()


def _write_marker(model_dir: Path) -> None:
    """Write the completion marker atomically into ``model_dir``.

    Parameters
    ----------
    model_dir : Path
        The directory to mark as complete.
    """
    marker = model_dir / COMPLETION_MARKER
    tmp = model_dir / f"{COMPLETION_MARKER}.tmp"
    tmp.write_text("ok")
    os.replace(tmp, marker)


def resolve() -> HostedModelSource | None:
    """Resolve an operator-supplied S3 model location, if configured.

    A download is considered complete only when ``COMPLETION_MARKER`` exists
    inside the cache directory.  A non-empty directory without the marker is
    treated as **partial** and re-downloaded in full (research R4 fix).

    Existing caches that pre-date the marker are also treated as incomplete
    and re-downloaded — a redundant re-download is far less harmful than
    serving a corrupt model.

    Returns
    -------
    HostedModelSource | None
        ``None`` when ``EMBER_MODEL_S3_URI`` is unset (the normal, unaffected
        ``REGISTRY``-based path applies). Otherwise the resolved, downloaded
        (or already-cached) model location.

    Raises
    ------
    RuntimeError
        If the URI is malformed, or if the download itself fails.
    """
    uri = os.environ.get(_URI_ENV)
    if not uri:
        return None
    bucket, prefix = _parse_uri(uri)
    model_dir = paths.hosted_model_cache(uri)
    if not _is_complete(model_dir):
        max_bytes = int(config.resolve("s3_max_bytes") or 0)
        s3.download_prefix(
            bucket, prefix, model_dir, f"{_URI_ENV}={uri!r}", max_bytes=max_bytes
        )
        _write_marker(model_dir)
    return HostedModelSource(uri=uri, model_dir=model_dir)
