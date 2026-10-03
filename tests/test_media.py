"""Media ref decoding: unit-level, no model load.

The advise wire format mirrors Cloudflare's hosted schema: data URIs or
``{content_type, base64}`` objects, decoded to RGB PIL images server-side.
"""

from __future__ import annotations

import base64
import io

import pytest
from ember import media
from PIL import Image


def _png_bytes(color: tuple[int, int, int] = (220, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _png_data_uri(color: tuple[int, int, int] = (220, 30, 30)) -> str:
    return "data:image/png;base64," + base64.b64encode(_png_bytes(color)).decode()


def test_decode_data_uri_returns_rgb_image():
    image = media.decode_ref(_png_data_uri())
    assert image.mode == "RGB"
    assert image.size == (8, 8)


def test_decode_base64_object_returns_rgb_image():
    ref = {
        "content_type": "image/png",
        "base64": base64.b64encode(_png_bytes()).decode(),
    }
    image = media.decode_ref(ref)
    assert image.mode == "RGB"
    assert image.size == (8, 8)


def test_decode_rejects_local_paths():
    with pytest.raises(ValueError, match="remote URLs and local paths"):
        media.decode_ref("receipt.png")


def test_decode_rejects_remote_urls():
    with pytest.raises(ValueError, match="remote URLs and local paths"):
        media.decode_ref("https://example.com/receipt.png")


def test_decode_rejects_unknown_content_type():
    with pytest.raises(ValueError, match="content_type must be one of"):
        media.decode_ref({"content_type": "image/gif", "base64": "AAAA"})


def test_decode_rejects_missing_base64_field():
    with pytest.raises(ValueError, match="requires a string 'base64' field"):
        media.decode_ref({"content_type": "image/png"})


def test_decode_rejects_invalid_base64():
    with pytest.raises(ValueError, match="not valid base64"):
        media.decode_ref("data:image/png;base64,not*base64!")


def test_decode_rejects_undecodable_bytes():
    with pytest.raises(ValueError, match="could not decode image"):
        media.decode_ref({"content_type": "image/png", "base64": "AAAA"})


def test_decode_rejects_unsupported_type():
    with pytest.raises(ValueError, match="unsupported image ref"):
        media.decode_ref(42)  # type: ignore[arg-type]


def test_decode_images_preserves_order_and_count():
    refs = [_png_data_uri((255, 0, 0)), _png_data_uri((0, 255, 0))]
    images = media.decode_images(refs)
    assert len(images) == 2
    assert all(image.mode == "RGB" for image in images)


def test_decode_videos_decodes_frames():
    video = [_png_data_uri(), _png_data_uri((0, 0, 255))]
    decoded = media.decode_videos([video])
    assert len(decoded) == 1
    assert [frame.size for frame in decoded[0]] == [(8, 8), (8, 8)]


def test_decode_videos_enforces_the_frame_cap():
    over_cap = [[_png_data_uri()] * (media.MAX_VIDEO_FRAMES + 1)]
    with pytest.raises(ValueError, match="too many video frames"):
        media.decode_videos(over_cap)


def test_decode_videos_rejects_a_non_list_video():
    with pytest.raises(ValueError, match="non-empty list of frame refs"):
        media.decode_videos([_png_data_uri()])  # type: ignore[list-item]
