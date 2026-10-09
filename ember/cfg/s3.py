"""AWS S3 download for an operator-supplied model location.

Used by :mod:`ember.serving.hosted` to download a model directly from an
``EMBER_MODEL_S3_URI`` (``s3://bucket/prefix``) when ember runs on a hosted
platform (e.g. Outerbounds) that supplies the model's location at start time.
Credentials are optional: when unconfigured, boto3's own default credential
chain applies — the expected case for a hosted deployment with an IAM role
attached to the compute (the usual Metaflow-managed S3 access pattern).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import config

_S3_CONNECT_TIMEOUT = 30
_S3_READ_TIMEOUT = 300


def s3_client() -> Any:
    """Construct an AWS S3 client, with or without explicit credentials.

    When both ``s3_access_key_id`` and ``s3_secret_access_key``
    are configured, they are passed explicitly. Otherwise, no credential
    kwargs are passed at all, and boto3's own default credential chain
    applies (environment variables, the shared AWS config/credentials files,
    or — the expected case for a hosted deployment with Metaflow-managed S3
    access — an IAM role attached to the compute, e.g. an Outerbounds
    execution environment). A
    partially-configured pair (only one of the two set) is treated as
    unconfigured, since boto3 rejects a half-explicit credential pair
    confusingly.

    Returns
    -------
    Any
        A ``boto3`` S3 client.

    Raises
    ------
    RuntimeError
        If constructing the client itself fails — wrapped so it surfaces
        through ``cli.main``'s ``RuntimeError``/``KeyError`` handler as a
        clean ``error: ...`` message (spec FR-009).
    """
    # import-placement:allow - deferred; boto3 must not load at module import
    import boto3
    from botocore.config import Config as BotocoreConfig

    access_key_id = config.resolve("s3_access_key_id")
    secret_access_key = config.resolve("s3_secret_access_key")
    region = config.resolve("s3_region")
    has_explicit_credentials = bool(access_key_id and secret_access_key)
    boto_config = BotocoreConfig(
        connect_timeout=_S3_CONNECT_TIMEOUT,
        read_timeout=_S3_READ_TIMEOUT,
    )
    try:
        if has_explicit_credentials:
            return boto3.client(
                "s3",
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region,
                config=boto_config,
            )
        return boto3.client("s3", region_name=region, config=boto_config)
    except ValueError as exc:
        raise RuntimeError(f"could not create an S3 client: {exc}") from exc


def download_prefix(
    bucket: str,
    prefix: str,
    dest: Path,
    label: str,
    max_bytes: int = 0,
) -> Path:
    """Download every object under an S3 bucket/prefix into a local directory.

    Parameters
    ----------
    bucket : str
        The S3 bucket to list and download from.
    prefix : str
        The object-key prefix within ``bucket`` (a trailing ``/`` is
        normalized away before use).
    dest : Path
        The local directory to download files into. Created if missing.
    label : str
        A human-readable name for the thing being downloaded, used only in
        error messages (e.g. the ``EMBER_MODEL_S3_URI`` value).
    max_bytes : int, optional
        Maximum total size in bytes permitted for the prefix (D-006). ``0``
        disables the size preflight entirely. When positive, the paginator
        accumulates ``Size`` totals before any download begins; if the total
        exceeds ``max_bytes`` a ``RuntimeError`` is raised without downloading
        any file.

    Returns
    -------
    Path
        ``dest``, once every object under the prefix has been downloaded.

    Raises
    ------
    RuntimeError
        If the S3 request fails, no objects exist under the prefix, or the
        total prefix size exceeds ``max_bytes``.
    """
    prefix = prefix.rstrip("/")
    client = s3_client()
    dest.mkdir(parents=True, exist_ok=True)
    # import-placement:allow - deferred with boto3 itself; avoids botocore
    # import at module load for users who never set EMBER_MODEL_S3_URI
    from botocore.exceptions import BotoCoreError, ClientError

    found = False
    objects: list[dict[str, object]] = []
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix}/"):
            for obj in page.get("Contents", []):
                key = str(obj["Key"])
                relative = key[len(prefix) + 1 :]
                if not relative:
                    continue
                found = True
                objects.append({"key": key, "size": int(obj.get("Size", 0))})
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(
            f"S3 download failed for {label} (s3://{bucket}/{prefix}/): {exc}"
        ) from exc
    if not found:
        raise RuntimeError(
            f"no objects found under s3://{bucket}/{prefix}/ for {label}"
        )
    # D-006: preflight size check — reject before downloading anything.
    if max_bytes > 0:
        total = sum(int(str(o["size"])) for o in objects)
        if total > max_bytes:
            raise RuntimeError(
                f"S3 prefix s3://{bucket}/{prefix}/ for {label} exceeds the "
                f"{max_bytes / 1024 / 1024:.0f} MB size cap "
                f"({total / 1024 / 1024:.0f} MB total). "
                "Raise EMBER_S3_MAX_BYTES or set it to 0 to disable the cap."
            )
    resolved_dest = dest.resolve()
    try:
        for obj in objects:
            key = str(obj["key"])
            relative = key[len(prefix) + 1 :]
            target = (dest / relative).resolve()
            if (
                not str(target).startswith(str(resolved_dest) + "/")
                and target != resolved_dest
            ):
                raise RuntimeError(
                    f"S3 key {key!r} for {label} resolves outside the download "
                    f"destination {dest} — possible path traversal attack"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(target))
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(
            f"S3 download failed for {label} (s3://{bucket}/{prefix}/): {exc}"
        ) from exc
    return dest
