"""The vendored filler corpus and the deterministic offset each item reads from."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

FILLER_PATH = Path(__file__).with_name("filler.txt")
FILLER_SHA256 = "f4b274b0250e9c6239797efa7a30a05c78d9fca9a5bd0e2de2ed613e715c57d5"
FILLER_SOURCE = "https://www.gutenberg.org/ebooks/2701.txt.utf-8"
FILLER_LICENCE = (
    "Public domain: Herman Melville, Moby-Dick; or, The Whale (eBook #2701), "
    "with the header, licence, and transcriber's note removed"
)


def load_filler(path: Path = FILLER_PATH, sha256: str = FILLER_SHA256) -> str:
    """Return the filler text after checking its SHA-256.

    Raises
    ------
    ValueError
        If the file's digest is not ``sha256``.
    """
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise ValueError(f"filler SHA-256 is {digest}, expected {sha256}")
    return data.decode("utf-8")


def filler_ids(tokenizer: Any, text: str | None = None) -> list[int]:
    """Tokenize the filler once, without special tokens."""
    source = load_filler() if text is None else text
    return list(tokenizer(source, add_special_tokens=False).input_ids)


def offset_for(item_id: str, needed: int, available: int) -> int:
    """Return the item's filler start: its id's SHA-256 modulo the free span.

    The offset leaves ``needed`` tokens before the end of ``available``.

    Raises
    ------
    ValueError
        If the filler is shorter than ``needed`` tokens.
    """
    span = available - needed
    if span < 0:
        raise ValueError(f"the filler has {available} tokens; an item needs {needed}")
    digest = int.from_bytes(hashlib.sha256(item_id.encode("utf-8")).digest(), "big")
    return digest % (span + 1)
