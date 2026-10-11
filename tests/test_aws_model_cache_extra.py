"""Extra tests for ModelCache: ensure_bucket, status, add, list, remove, destroy."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BUCKET = "ember-model-cache-123456789012-us-east-1"
_REVISION = "17f0b0ad64efb65d273590632833508766b2aae6"
_PREFIX = "models/"
_CACHE_STACK_NAME = "ember-model-cache"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_clients(
    *,
    cache_stack_exists: bool = False,
    s3_objects: dict[str, bytes] | None = None,
    deployment_stacks: list[str] | None = None,
) -> Any:
    """Build a fake AwsClients-shaped object."""
    clients = MagicMock()
    _objects: dict[str, bytes] = s3_objects or {}

    # CFN
    from botocore.exceptions import ClientError

    def describe_stacks(StackName: str) -> dict[str, Any]:  # noqa: N803
        if StackName == _CACHE_STACK_NAME and cache_stack_exists:
            return {
                "Stacks": [
                    {
                        "StackName": _CACHE_STACK_NAME,
                        "StackStatus": "CREATE_COMPLETE",
                        "Outputs": [
                            {"OutputKey": "BucketName", "OutputValue": _BUCKET}
                        ],
                    }
                ]
            }
        raise ClientError(
            {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
            "DescribeStacks",
        )

    clients.cfn.describe_stacks.side_effect = describe_stacks
    clients.cfn.create_stack.return_value = {
        "StackId": "arn:aws:cfn:us-east-1:123:stack/x"
    }
    clients.cfn.get_waiter.return_value = MagicMock()

    # list_stacks for destroy guard
    active_stacks = []
    for name in deployment_stacks or []:
        active_stacks.append({"StackName": name, "StackStatus": "CREATE_COMPLETE"})
    clients.cfn.list_stacks.return_value = {"StackSummaries": active_stacks}
    clients.cfn.delete_stack.return_value = {}

    # S3
    def head_object(Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if Key in _objects:
            data = _objects[Key]
            return {
                "ContentLength": len(data),
                "Metadata": {"sha256": _sha256(data)},
            }
        raise ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )

    def get_object(Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if Key in _objects:
            return {"Body": io.BytesIO(_objects[Key])}
        raise ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
        )

    def list_objects_v2(Bucket: str, Prefix: str = "") -> dict[str, Any]:  # noqa: N803
        contents = [
            {"Key": k, "Size": len(v)}
            for k, v in _objects.items()
            if k.startswith(Prefix)
        ]
        return {"Contents": contents, "IsTruncated": False}

    clients.s3.head_object.side_effect = head_object
    clients.s3.get_object.side_effect = get_object
    clients.s3.put_object.return_value = {}
    clients.s3.delete_object.return_value = {}
    clients.s3.list_objects_v2.side_effect = list_objects_v2

    return clients


def _make_cache(clients: Any, downloader: Any = None) -> Any:
    from ember_aws.model_cache import ModelCache

    return ModelCache(clients=clients, downloader=downloader)


# ---------------------------------------------------------------------------
# ensure_bucket()
# ---------------------------------------------------------------------------


class TestEnsureBucket:
    """ModelCache.ensure_bucket() creates the stack when absent."""

    def test_returns_existing_bucket_when_stack_exists(self) -> None:
        """ensure_bucket() returns the bucket name when the stack already exists."""
        clients = _make_clients(cache_stack_exists=True)
        mc = _make_cache(clients)
        bucket = mc.ensure_bucket()
        assert bucket == _BUCKET
        clients.cfn.create_stack.assert_not_called()

    def test_creates_stack_when_absent(self, tmp_path: Any) -> None:
        """ensure_bucket() creates the cache stack when it does not exist."""
        # After creation, the stack should exist
        call_count = 0

        from botocore.exceptions import ClientError

        def describe_stacks_side_effect(StackName: str) -> dict[str, Any]:  # noqa: N803
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                # After create, return the stack
                return {
                    "Stacks": [
                        {
                            "StackName": _CACHE_STACK_NAME,
                            "StackStatus": "CREATE_COMPLETE",
                            "Outputs": [
                                {"OutputKey": "BucketName", "OutputValue": _BUCKET}
                            ],
                        }
                    ]
                }
            raise ClientError(
                {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
                "DescribeStacks",
            )

        clients = _make_clients(cache_stack_exists=False)
        clients.cfn.describe_stacks.side_effect = describe_stacks_side_effect

        # Patch the template path to avoid reading the real file
        from unittest.mock import patch

        with patch.object(
            Path,
            "read_text",
            return_value="AWSTemplateFormatVersion: '2010-09-09'",
        ):
            mc = _make_cache(clients)
            bucket = mc.ensure_bucket()

        assert bucket == _BUCKET
        clients.cfn.create_stack.assert_called_once()

    def test_raises_when_bucket_not_in_outputs_after_create(
        self, tmp_path: Any
    ) -> None:
        """ensure_bucket() raises RuntimeError when BucketName output is missing."""
        from botocore.exceptions import ClientError

        call_count = 0

        def describe_stacks_side_effect(StackName: str) -> dict[str, Any]:  # noqa: N803
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                # Stack exists but no BucketName output
                return {
                    "Stacks": [
                        {
                            "StackName": _CACHE_STACK_NAME,
                            "StackStatus": "CREATE_COMPLETE",
                            "Outputs": [],
                        }
                    ]
                }
            raise ClientError(
                {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
                "DescribeStacks",
            )

        clients = _make_clients(cache_stack_exists=False)
        clients.cfn.describe_stacks.side_effect = describe_stacks_side_effect

        from unittest.mock import patch

        with patch.object(
            Path,
            "read_text",
            return_value="AWSTemplateFormatVersion: '2010-09-09'",
        ):
            mc = _make_cache(clients)
            with pytest.raises(RuntimeError, match="BucketName output not found"):
                mc.ensure_bucket()


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------


class TestModelCacheStatus:
    """ModelCache.status() returns correct status strings."""

    def test_returns_absent_when_no_stack(self) -> None:
        """status() returns 'absent' when the cache stack does not exist."""
        clients = _make_clients(cache_stack_exists=False)
        mc = _make_cache(clients)
        result = mc.status("flash", _REVISION)
        assert result == "absent"

    def test_returns_absent_when_no_manifest(self) -> None:
        """status() returns 'absent' when the manifest key does not exist."""
        clients = _make_clients(cache_stack_exists=True, s3_objects={})
        mc = _make_cache(clients)
        result = mc.status("flash", _REVISION, bucket=_BUCKET)
        assert result == "absent"

    def test_returns_partial_when_manifest_unreadable(self) -> None:
        """status() returns 'partial' when the manifest cannot be parsed."""
        manifest_key = f"{_PREFIX}flash/{_REVISION}/manifest.json"
        clients = _make_clients(
            cache_stack_exists=True,
            s3_objects={manifest_key: b"not valid json"},
        )
        mc = _make_cache(clients)
        result = mc.status("flash", _REVISION, bucket=_BUCKET)
        assert result == "partial"

    def test_returns_partial_when_file_size_mismatch(self) -> None:
        """status() returns 'partial' when a file's size does not match the manifest."""
        manifest_key = f"{_PREFIX}flash/{_REVISION}/manifest.json"
        manifest = {
            "files": [{"path": "model.safetensors", "size": 9999, "sha256": "abc"}]
        }
        # The actual object has a different size
        file_key = f"{_PREFIX}flash/{_REVISION}/model.safetensors"
        clients = _make_clients(
            cache_stack_exists=True,
            s3_objects={
                manifest_key: json.dumps(manifest).encode(),
                file_key: b"x" * 100,  # size 100, not 9999
            },
        )
        mc = _make_cache(clients)
        result = mc.status("flash", _REVISION, bucket=_BUCKET)
        assert result == "partial"

    def test_returns_partial_when_file_missing(self) -> None:
        """status() returns 'partial' when a manifest file is missing from S3."""
        manifest_key = f"{_PREFIX}flash/{_REVISION}/manifest.json"
        manifest = {
            "files": [{"path": "model.safetensors", "size": 100, "sha256": "abc"}]
        }
        # File is NOT in s3_objects
        clients = _make_clients(
            cache_stack_exists=True,
            s3_objects={manifest_key: json.dumps(manifest).encode()},
        )
        mc = _make_cache(clients)
        result = mc.status("flash", _REVISION, bucket=_BUCKET)
        assert result == "partial"

    def test_returns_complete_when_all_files_match(self) -> None:
        """status() returns 'complete' when all manifest files match."""
        file_data = b"x" * 100
        manifest_key = f"{_PREFIX}flash/{_REVISION}/manifest.json"
        file_key = f"{_PREFIX}flash/{_REVISION}/model.safetensors"
        manifest = {
            "files": [
                {
                    "path": "model.safetensors",
                    "size": len(file_data),
                    "sha256": _sha256(file_data),
                }
            ]
        }
        clients = _make_clients(
            cache_stack_exists=True,
            s3_objects={
                manifest_key: json.dumps(manifest).encode(),
                file_key: file_data,
            },
        )
        mc = _make_cache(clients)
        result = mc.status("flash", _REVISION, bucket=_BUCKET)
        assert result == "complete"


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------


class TestModelCacheAdd:
    """ModelCache.add() downloads and uploads a model."""

    def test_add_raises_for_unknown_model(self) -> None:
        """add() raises ValueError for an unknown model key."""
        clients = _make_clients(cache_stack_exists=True)
        mc = _make_cache(clients)
        with pytest.raises(ValueError, match="unknown model"):
            mc.add("nonexistent-model", bucket=_BUCKET)

    def test_add_skips_when_already_complete(self, capsys: Any) -> None:
        """add() prints 'already complete' and returns when status is complete."""
        file_data = b"x" * 100
        manifest_key = f"{_PREFIX}flash/{_REVISION}/manifest.json"
        file_key = f"{_PREFIX}flash/{_REVISION}/model.safetensors"
        manifest = {
            "files": [
                {
                    "path": "model.safetensors",
                    "size": len(file_data),
                    "sha256": _sha256(file_data),
                }
            ]
        }
        clients = _make_clients(
            cache_stack_exists=True,
            s3_objects={
                manifest_key: json.dumps(manifest).encode(),
                file_key: file_data,
            },
        )
        mc = _make_cache(clients)
        mc.add("flash", bucket=_BUCKET)
        captured = capsys.readouterr()
        assert "already complete" in captured.out

    def test_add_calls_downloader_when_not_complete(self, tmp_path: Any) -> None:
        """add() calls the downloader when the cache is not complete."""
        # Create a fake local model directory
        local_dir = tmp_path / "model"
        local_dir.mkdir()
        (local_dir / "config.json").write_text("{}")

        def fake_downloader(**kwargs: Any) -> str:
            return str(local_dir)

        clients = _make_clients(cache_stack_exists=True, s3_objects={})
        mc = _make_cache(clients, downloader=fake_downloader)
        mc.add("flash", bucket=_BUCKET)
        # Should have called put_object for the manifest
        clients.s3.put_object.assert_called()


# ---------------------------------------------------------------------------
# list()
# ---------------------------------------------------------------------------


class TestModelCacheList:
    """ModelCache.list() returns cached model entries."""

    def test_list_returns_empty_when_no_stack(self) -> None:
        """list() returns [] when the cache stack does not exist."""
        clients = _make_clients(cache_stack_exists=False)
        mc = _make_cache(clients)
        result = mc.list()
        assert result == []

    def test_list_returns_empty_when_no_manifests(self) -> None:
        """list() returns [] when there are no manifest files."""
        clients = _make_clients(cache_stack_exists=True, s3_objects={})
        mc = _make_cache(clients)
        result = mc.list(bucket=_BUCKET)
        assert result == []

    def test_list_returns_entries_for_each_manifest(self) -> None:
        """list() returns one entry per manifest file found."""
        manifest_key = f"{_PREFIX}flash/{_REVISION}/manifest.json"
        manifest = {"files": []}
        clients = _make_clients(
            cache_stack_exists=True,
            s3_objects={manifest_key: json.dumps(manifest).encode()},
        )
        mc = _make_cache(clients)
        result = mc.list(bucket=_BUCKET)
        assert len(result) == 1
        assert result[0]["model"] == "flash"
        assert result[0]["revision"] == _REVISION

    def test_list_uses_stack_bucket_when_none_given(self) -> None:
        """list() uses the cache stack bucket when bucket=None."""
        clients = _make_clients(cache_stack_exists=True, s3_objects={})
        mc = _make_cache(clients)
        mc.list()
        # Should have called list_objects_v2 on the stack bucket
        clients.s3.list_objects_v2.assert_called()


# ---------------------------------------------------------------------------
# remove()
# ---------------------------------------------------------------------------


class TestModelCacheRemove:
    """ModelCache.remove() deletes model files from S3."""

    def test_remove_returns_early_when_no_stack(self) -> None:
        """remove() returns without error when the cache stack does not exist."""
        clients = _make_clients(cache_stack_exists=False)
        mc = _make_cache(clients)
        mc.remove("flash", _REVISION)  # Should not raise
        clients.s3.delete_object.assert_not_called()

    def test_remove_deletes_all_objects_under_prefix(self) -> None:
        """remove() deletes all S3 objects under the model/revision prefix."""
        file_key = f"{_PREFIX}flash/{_REVISION}/model.safetensors"
        manifest_key = f"{_PREFIX}flash/{_REVISION}/manifest.json"
        clients = _make_clients(
            cache_stack_exists=True,
            s3_objects={
                file_key: b"data",
                manifest_key: b"{}",
            },
        )
        # Patch check_not_in_use to not raise
        from unittest.mock import patch

        with patch("ember_aws.model_cache.check_not_in_use"):
            mc = _make_cache(clients)
            mc.remove("flash", _REVISION, bucket=_BUCKET)

        assert clients.s3.delete_object.call_count >= 1


# ---------------------------------------------------------------------------
# destroy()
# ---------------------------------------------------------------------------


class TestModelCacheDestroy:
    """ModelCache.destroy() deletes the bucket and stack."""

    def test_destroy_returns_early_when_no_stack(self) -> None:
        """destroy() returns without error when the cache stack does not exist."""
        clients = _make_clients(cache_stack_exists=False)
        mc = _make_cache(clients)
        mc.destroy(confirm="any-bucket")  # Should not raise
        clients.cfn.delete_stack.assert_not_called()

    def test_destroy_raises_confirmation_error_on_mismatch(self) -> None:
        """destroy() raises ConfirmationError when confirm != bucket name."""
        from ember_aws.model_cache import ConfirmationError

        clients = _make_clients(cache_stack_exists=True)
        mc = _make_cache(clients)
        with pytest.raises(ConfirmationError):
            mc.destroy(confirm="wrong-bucket-name", bucket=_BUCKET)

    def test_destroy_raises_cache_in_use_when_deployments_exist(self) -> None:
        """destroy() raises CacheInUseError when ember deployments exist."""
        from ember_aws.model_cache import CacheInUseError

        clients = _make_clients(
            cache_stack_exists=True,
            deployment_stacks=["ember-default"],
        )
        mc = _make_cache(clients)
        with pytest.raises(CacheInUseError):
            mc.destroy(confirm=_BUCKET, bucket=_BUCKET)

    def test_destroy_deletes_objects_and_stack_when_confirmed(self) -> None:
        """destroy() deletes all S3 objects and the CFN stack when confirmed."""
        file_key = f"{_PREFIX}flash/{_REVISION}/model.safetensors"
        clients = _make_clients(
            cache_stack_exists=True,
            s3_objects={file_key: b"data"},
            deployment_stacks=[],
        )
        mc = _make_cache(clients)
        mc.destroy(confirm=_BUCKET)
        clients.s3.delete_object.assert_called()
        clients.s3.delete_bucket.assert_called_once_with(Bucket=_BUCKET)
        clients.cfn.delete_stack.assert_called_once_with(StackName=_CACHE_STACK_NAME)

    def test_destroy_uses_stack_bucket_when_none_given(self) -> None:
        """destroy() uses the cache stack bucket when bucket=None."""
        clients = _make_clients(
            cache_stack_exists=True,
            s3_objects={},
            deployment_stacks=[],
        )
        mc = _make_cache(clients)
        mc.destroy(confirm=_BUCKET)
        clients.cfn.delete_stack.assert_called_once()
