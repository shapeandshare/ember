"""Extra tests for CacheUploader: skip existing, upload new files, manifest last."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_s3_client(
    *,
    existing_objects: dict[str, bytes] | None = None,
) -> Any:
    """Build a fake S3 client."""
    s3 = MagicMock()
    _objects: dict[str, bytes] = existing_objects or {}

    def head_object(Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if Key in _objects:
            data = _objects[Key]
            return {
                "ContentLength": len(data),
                "Metadata": {"sha256": _sha256(data)},
            }
        from botocore.exceptions import ClientError

        raise ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )

    s3.head_object.side_effect = head_object
    s3.put_object.return_value = {}
    s3.upload_file.return_value = None
    return s3


# ---------------------------------------------------------------------------
# CacheUploader.upload()
# ---------------------------------------------------------------------------


class TestCacheUploaderUpload:
    """CacheUploader.upload() uploads files and writes the manifest last."""

    def test_uploads_new_files(self, tmp_path: Path) -> None:
        """upload() streams each new file and writes the manifest."""
        from ember_aws.cache_uploader import CacheUploader

        # Create a fake model directory with one file
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "config.json").write_bytes(b'{"model": "flash"}')

        s3 = _make_s3_client()
        uploader = CacheUploader(s3_client=s3)
        uploader.upload(
            model="flash",
            revision="rev123",
            bucket="my-bucket",
            prefix="models/",
            local_path=model_dir,
        )

        # The file streams through upload_file; the manifest is the put_object.
        assert s3.upload_file.call_count == 1
        assert s3.put_object.call_count == 1

    def test_streams_model_shards_via_upload_file(self, tmp_path: Path) -> None:
        """upload() streams each file with upload_file, preserving sha metadata."""
        from ember_aws.cache_uploader import CacheUploader

        file_name = "model-00001-of-00004.safetensors"
        file_data = b"weights"
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / file_name).write_bytes(file_data)

        s3 = _make_s3_client()
        uploader = CacheUploader(s3_client=s3)
        uploader.upload(
            model="flash",
            revision="rev123",
            bucket="my-bucket",
            prefix="models/",
            local_path=model_dir,
        )

        [call] = s3.upload_file.call_args_list
        assert call.kwargs["Filename"] == str(model_dir / file_name)
        assert call.kwargs["Bucket"] == "my-bucket"
        assert call.kwargs["Key"] == f"models/flash/rev123/{file_name}"
        assert call.kwargs["ExtraArgs"]["Metadata"]["sha256"] == _sha256(file_data)

    def test_manifest_written_last(self, tmp_path: Path) -> None:
        """upload() writes the manifest as the final put_object call."""
        from ember_aws.cache_uploader import CacheUploader

        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "config.json").write_bytes(b'{"model": "flash"}')

        s3 = _make_s3_client()
        uploader = CacheUploader(s3_client=s3)
        uploader.upload(
            model="flash",
            revision="rev123",
            bucket="my-bucket",
            prefix="models/",
            local_path=model_dir,
        )

        # The last put_object call should be for the manifest
        last_call = s3.put_object.call_args_list[-1]
        key = last_call.kwargs.get(
            "Key", last_call.args[1] if len(last_call.args) > 1 else ""
        )
        assert "manifest.json" in key

    def test_skips_already_uploaded_files(self, tmp_path: Path) -> None:
        """upload() skips files that already exist with matching size and sha256."""
        from ember_aws.cache_uploader import CacheUploader

        model_dir = tmp_path / "model"
        model_dir.mkdir()
        file_data = b'{"model": "flash"}'
        (model_dir / "config.json").write_bytes(file_data)

        # Pre-populate the S3 client with the existing file
        existing_key = "models/flash/rev123/config.json"
        s3 = _make_s3_client(existing_objects={existing_key: file_data})
        uploader = CacheUploader(s3_client=s3)
        uploader.upload(
            model="flash",
            revision="rev123",
            bucket="my-bucket",
            prefix="models/",
            local_path=model_dir,
        )

        # Only the manifest should be uploaded (the file was skipped)
        put_keys = [call.kwargs.get("Key", "") for call in s3.put_object.call_args_list]
        assert all("manifest.json" in k or k == "" for k in put_keys if k)
        # config.json should NOT be uploaded through either path
        upload_keys = [
            call.kwargs.get("Key", "") for call in s3.upload_file.call_args_list
        ]
        assert not any("config.json" in k for k in upload_keys)
        assert not any("config.json" in k for k in put_keys)

    def test_uploads_file_when_size_differs(self, tmp_path: Path) -> None:
        """upload() re-uploads a file when the existing size differs."""
        from ember_aws.cache_uploader import CacheUploader

        model_dir = tmp_path / "model"
        model_dir.mkdir()
        file_data = b'{"model": "flash"}'
        (model_dir / "config.json").write_bytes(file_data)

        # Pre-populate with a different-sized file
        existing_key = "models/flash/rev123/config.json"
        s3 = _make_s3_client(existing_objects={existing_key: b"different content"})
        uploader = CacheUploader(s3_client=s3)
        uploader.upload(
            model="flash",
            revision="rev123",
            bucket="my-bucket",
            prefix="models/",
            local_path=model_dir,
        )

        # config.json should be re-uploaded (via the streaming transfer)
        upload_keys = [
            call.kwargs.get("Key", "") for call in s3.upload_file.call_args_list
        ]
        assert any("config.json" in k for k in upload_keys)

    def test_manifest_contains_uploaded_files(self, tmp_path: Path) -> None:
        """upload() writes a manifest that lists all uploaded files."""
        import json

        from ember_aws.cache_uploader import CacheUploader

        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "config.json").write_bytes(b'{"model": "flash"}')

        manifest_body: list[bytes] = []

        def capture_put_object(**kwargs: Any) -> dict[str, Any]:
            if "manifest.json" in kwargs.get("Key", ""):
                manifest_body.append(kwargs.get("Body", b""))
            return {}

        s3 = _make_s3_client()
        s3.put_object.side_effect = capture_put_object

        uploader = CacheUploader(s3_client=s3)
        uploader.upload(
            model="flash",
            revision="rev123",
            bucket="my-bucket",
            prefix="models/",
            local_path=model_dir,
        )

        assert len(manifest_body) == 1
        manifest = json.loads(manifest_body[0])
        assert manifest["model"] == "flash"
        assert manifest["revision"] == "rev123"
        assert len(manifest["files"]) >= 1

    def test_empty_directory_writes_empty_manifest(self, tmp_path: Path) -> None:
        """upload() writes a manifest with no files for an empty directory."""
        import json

        from ember_aws.cache_uploader import CacheUploader

        model_dir = tmp_path / "model"
        model_dir.mkdir()
        # No files in the directory

        manifest_body: list[bytes] = []

        def capture_put_object(**kwargs: Any) -> dict[str, Any]:
            if "manifest.json" in kwargs.get("Key", ""):
                manifest_body.append(kwargs.get("Body", b""))
            return {}

        s3 = _make_s3_client()
        s3.put_object.side_effect = capture_put_object

        uploader = CacheUploader(s3_client=s3)
        uploader.upload(
            model="flash",
            revision="rev123",
            bucket="my-bucket",
            prefix="models/",
            local_path=model_dir,
        )

        assert len(manifest_body) == 1
        manifest = json.loads(manifest_body[0])
        assert manifest["files"] == []
