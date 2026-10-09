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
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ..cfg import config, paths, s3

_URI_ENV = "EMBER_MODEL_S3_URI"


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


def resolve() -> HostedModelSource | None:
    """Resolve an operator-supplied S3 model location, if configured.

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
    if not model_dir.is_dir() or not any(model_dir.iterdir()):
        max_bytes = int(config.resolve("s3_max_bytes") or 0)
        s3.download_prefix(
            bucket, prefix, model_dir, f"{_URI_ENV}={uri!r}", max_bytes=max_bytes
        )
    return HostedModelSource(uri=uri, model_dir=model_dir)
