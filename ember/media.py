"""Decode JSON-serializable media refs into PIL images for Clef's encoder.

The ``advise`` tool crosses MCP and HTTP as JSON, but Clef's ``encode_record``
wants real PIL images: image refs are passed straight to the processor, and
video frames *must* already be decoded (string frames need ``torchcodec``, which
we do not ship). So ember decodes media refs itself, in the model-server process
only — ``mcp_server`` forwards strings and never imports this module.

The wire format mirrors Cloudflare's hosted Clef API: an image is either a
``data:image/<type>;base64,<bytes>`` string or a ``{"content_type": ...,
"base64": ...}`` object. Remote URLs and local file paths are deliberately
rejected — an agent-supplied ref must not make the warm server fetch arbitrary
URLs or read host files.
"""

from __future__ import annotations

import base64
import binascii
import io
from typing import Any

from PIL import Image

#: Cloudflare's hosted schema accepts these image types only.
ALLOWED_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})

#: Upper bound on decoded frames across all videos, to bound MPS memory.
MAX_VIDEO_FRAMES = 64

#: A JSON media reference: a data URI string or a {content_type, base64} object.
MediaRef = str | dict[str, Any]


def _decode_bytes(raw: bytes, source: str) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise ValueError(f"could not decode image from {source}: {exc}") from exc
    return image.convert("RGB")


def _decode_base64(payload: str, source: str) -> Image.Image:
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{source} is not valid base64: {exc}") from exc
    return _decode_bytes(raw, source)


def decode_ref(ref: MediaRef) -> Image.Image:
    """Decode one media ref (data URI or base64 object) into an RGB image."""
    if isinstance(ref, dict):
        content_type = str(ref.get("content_type", "")).lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            allowed = ", ".join(sorted(ALLOWED_CONTENT_TYPES))
            raise ValueError(f"content_type must be one of: {allowed}")
        payload = ref.get("base64")
        if not isinstance(payload, str):
            raise ValueError("an image object requires a string 'base64' field")
        return _decode_base64(payload, f"a {content_type} object")
    if isinstance(ref, str):
        if ref.startswith("data:"):
            header, _, payload = ref.partition(",")
            if ";base64" not in header or not payload:
                raise ValueError("a data URI must be base64-encoded")
            return _decode_base64(payload, "a data URI")
        raise ValueError(
            "an image ref must be a data: URI or a {content_type, base64} object; "
            "remote URLs and local paths are not accepted"
        )
    raise ValueError(f"unsupported image ref of type {type(ref).__name__}")


def decode_images(refs: list[MediaRef]) -> list[Image.Image]:
    """Decode a list of image refs, preserving order."""
    return [decode_ref(ref) for ref in refs]


def decode_videos(
    videos: list[list[MediaRef]], max_frames: int = MAX_VIDEO_FRAMES
) -> list[list[Image.Image]]:
    """Decode each video's frame refs, enforcing a total frame cap."""
    decoded: list[list[Image.Image]] = []
    total = 0
    for frames in videos:
        if not isinstance(frames, list) or not frames:
            raise ValueError("each video must be a non-empty list of frame refs")
        total += len(frames)
        if total > max_frames:
            raise ValueError(
                f"too many video frames: {total} exceeds the {max_frames} frame cap"
            )
        decoded.append([decode_ref(frame) for frame in frames])
    return decoded
