"""File-level helpers for the S3 model cache: hashing and extension filtering."""

from __future__ import annotations

import hashlib
from pathlib import Path

#: Multipart upload threshold: 64 MiB.
MULTIPART_THRESHOLD = 64 * 1024 * 1024

#: Maximum concurrent S3 upload threads.
MAX_CONCURRENCY = 16

#: Files included in the model upload (same allowlist as ember/models.py).
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".json",
        ".safetensors",
        ".py",
        ".txt",
        ".md",
        ".model",
        ".bin",
        ".pt",
        ".pth",
        ".gguf",
        ".ggml",
    }
)


def sha256_file(path: Path) -> str:
    """Compute the hex-encoded SHA-256 digest of a file.

    Parameters
    ----------
    path : Path
        Path to the file.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_allowed(path: Path) -> bool:
    """Return True if the file should be uploaded.

    Parameters
    ----------
    path : Path
        File path to check.

    Returns
    -------
    bool
        ``True`` if the file extension is in the allowlist or has no extension.
    """
    return path.suffix.lower() in ALLOWED_EXTENSIONS or path.suffix == ""
