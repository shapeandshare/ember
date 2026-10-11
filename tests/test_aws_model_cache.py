"""Tests for ModelCache, CachedModel, and CachedFile (T019)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from ember_aws.cached_model import CachedFile, CachedModel
from ember_aws.model_cache import ModelCache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BUCKET = "ember-model-cache-123456789012-us-east-1"
_REVISION = "17f0b0ad64efb65d273590632833508766b2aae6"
_PREFIX = "models/"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_s3_client(
    *,
    stack_exists: bool = False,
    objects: dict[str, bytes] | None = None,
) -> Any:
    """Return a mock S3 client."""
    s3 = MagicMock()
    _objects: dict[str, bytes] = objects or {}

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

    def get_object(Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if Key in _objects:
            import io

            return {"Body": io.BytesIO(_objects[Key])}
        from botocore.exceptions import ClientError

        raise ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
        )

    s3.head_object.side_effect = head_object
    s3.get_object.side_effect = get_object
    s3.put_object.return_value = {}
    s3.delete_object.return_value = {}
    s3.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}
    return s3


def _make_cfn_client(
    *,
    cache_stack_exists: bool = False,
    deployment_stacks: list[dict[str, Any]] | None = None,
) -> Any:
    """Return a mock CloudFormation client."""
    cfn = MagicMock()
    from botocore.exceptions import ClientError

    def describe_stacks(StackName: str) -> dict[str, Any]:  # noqa: N803
        if StackName == "ember-model-cache" and cache_stack_exists:
            return {
                "Stacks": [
                    {
                        "StackName": "ember-model-cache",
                        "StackStatus": "CREATE_COMPLETE",
                        "Outputs": [
                            {"OutputKey": "BucketName", "OutputValue": _BUCKET}
                        ],
                    }
                ]
            }
        raise ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack does not exist"}},
            "DescribeStacks",
        )

    cfn.describe_stacks.side_effect = describe_stacks
    cfn.create_stack.return_value = {
        "StackId": ("arn:aws:cloudformation:us-east-1:123:stack/ember-model-cache/abc")
    }
    cfn.get_waiter.return_value = MagicMock()

    # For listing deployment stacks
    stacks = deployment_stacks or []
    cfn.list_stacks.return_value = {"StackSummaries": stacks}
    cfn.describe_stack_resource.return_value = {}

    return cfn


def _make_aws_clients(
    s3: Any = None,
    cfn: Any = None,
) -> Any:
    clients = MagicMock()
    clients.s3 = s3 or _make_s3_client()
    clients.cfn = cfn or _make_cfn_client()
    clients.sts = MagicMock()
    clients.sts.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:user/test",
    }
    return clients


def _make_fake_downloader(tmp_path: Path, files: dict[str, bytes]) -> Any:
    """Return a fake snapshot_download that writes files to tmp_path."""

    def downloader(
        repo_id: str,
        revision: str | None = None,
        local_dir: str | None = None,
        **kwargs: Any,
    ) -> str:
        dest = Path(local_dir) if local_dir else tmp_path
        dest.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (dest / name).write_bytes(data)
        return str(dest)

    return downloader


# ---------------------------------------------------------------------------
# CachedFile and CachedModel models
# ---------------------------------------------------------------------------


def test_cached_file_fields() -> None:
    """CachedFile has path, size, and sha256."""
    cf = CachedFile(path="config.json", size=42, sha256="abc123")
    assert cf.path == "config.json"
    assert cf.size == 42
    assert cf.sha256 == "abc123"


def test_cached_model_fields() -> None:
    """CachedModel has model, revision, s3_uri, total_bytes, and files."""
    cm = CachedModel(
        model="flash",
        revision=_REVISION,
        s3_uri=f"s3://{_BUCKET}/models/flash/{_REVISION}",
        total_bytes=1024,
        files=[CachedFile(path="config.json", size=1024, sha256="abc")],
    )
    assert cm.model == "flash"
    assert cm.revision == _REVISION
    assert len(cm.files) == 1


# ---------------------------------------------------------------------------
# cache add — creates stack only if absent
# ---------------------------------------------------------------------------


def test_cache_add_creates_stack_when_absent(tmp_path: Path) -> None:
    """cache add creates the ember-model-cache stack when it does not exist."""
    from botocore.exceptions import ClientError

    file_data = b"fake model weights"
    downloader = _make_fake_downloader(tmp_path, {"config.json": file_data})
    cfn = _make_cfn_client(cache_stack_exists=False)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    # First call: stack absent; second call (after create): stack present.
    cfn.describe_stacks.side_effect = [
        ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack does not exist"}},
            "DescribeStacks",
        ),
        {
            "Stacks": [
                {
                    "StackName": "ember-model-cache",
                    "StackStatus": "CREATE_COMPLETE",
                    "Outputs": [{"OutputKey": "BucketName", "OutputValue": _BUCKET}],
                }
            ]
        },
    ]

    cache = ModelCache(clients=clients, downloader=downloader)
    # No explicit bucket → triggers ensure_bucket() → create_stack
    cache.add("flash", prefix=_PREFIX)

    cfn.create_stack.assert_called_once()


def test_cache_add_skips_stack_creation_when_exists(tmp_path: Path) -> None:
    """cache add does not create the stack when it already exists."""
    file_data = b"fake model weights"
    downloader = _make_fake_downloader(tmp_path, {"config.json": file_data})
    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients, downloader=downloader)
    cache.add("flash", bucket=_BUCKET, prefix=_PREFIX)

    cfn.create_stack.assert_not_called()


# ---------------------------------------------------------------------------
# cache add — uploads files and writes manifest last
# ---------------------------------------------------------------------------


def test_cache_add_uploads_all_files(tmp_path: Path) -> None:
    """cache add uploads every file under models/<model>/<revision>/."""
    files = {
        "config.json": b'{"model": "flash"}',
        "model.safetensors": b"weights-data",
    }
    downloader = _make_fake_downloader(tmp_path, files)
    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients, downloader=downloader)
    cache.add("flash", bucket=_BUCKET, prefix=_PREFIX)

    # Files stream through upload_file; only the manifest is a put_object.
    upload_keys = [c.kwargs.get("Key", "") for c in s3.upload_file.call_args_list]
    assert any("config.json" in k for k in upload_keys)
    assert any("model.safetensors" in k for k in upload_keys)


def test_cache_add_manifest_is_last_put(tmp_path: Path) -> None:
    """manifest.json is the last put_object call."""
    files = {
        "config.json": b'{"model": "flash"}',
        "model.safetensors": b"weights-data",
    }
    downloader = _make_fake_downloader(tmp_path, files)
    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients, downloader=downloader)
    cache.add("flash", bucket=_BUCKET, prefix=_PREFIX)

    put_calls = s3.put_object.call_args_list
    assert len(put_calls) > 0
    last_key = put_calls[-1].kwargs.get("Key", "")
    assert "manifest.json" in last_key


def test_cache_add_manifest_structure(tmp_path: Path) -> None:
    """manifest.json has model, revision, files list, and total_bytes."""
    file_data = b"fake weights"
    files = {"config.json": file_data}
    downloader = _make_fake_downloader(tmp_path, files)
    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients, downloader=downloader)
    cache.add("flash", bucket=_BUCKET, prefix=_PREFIX)

    # Find the manifest put_object call
    manifest_call = next(
        c
        for c in s3.put_object.call_args_list
        if "manifest.json" in c.kwargs.get("Key", "")
    )
    body = json.loads(manifest_call.kwargs["Body"])
    assert body["model"] == "flash"
    assert "revision" in body
    assert "files" in body
    assert "total_bytes" in body
    assert isinstance(body["files"], list)
    for f in body["files"]:
        assert "path" in f
        assert "size" in f
        assert "sha256" in f


# ---------------------------------------------------------------------------
# cache add — second run skips already-uploaded files
# ---------------------------------------------------------------------------


def test_cache_add_second_run_skips_complete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A second cache add with all files present prints 'already complete'."""
    file_data = b"fake weights"
    files = {"config.json": file_data}
    downloader = _make_fake_downloader(tmp_path, files)
    cfn = _make_cfn_client(cache_stack_exists=True)

    # S3 already has the file and manifest
    manifest = {
        "model": "flash",
        "revision": _REVISION,
        "files": [
            {
                "path": "config.json",
                "size": len(file_data),
                "sha256": _sha256(file_data),
            }
        ],
        "total_bytes": len(file_data),
    }
    manifest_bytes = json.dumps(manifest).encode()
    existing_objects = {
        f"models/flash/{_REVISION}/config.json": file_data,
        f"models/flash/{_REVISION}/manifest.json": manifest_bytes,
    }
    s3 = _make_s3_client(objects=existing_objects)
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients, downloader=downloader)
    cache.add("flash", bucket=_BUCKET, prefix=_PREFIX)

    out = capsys.readouterr().out
    assert "already complete" in out or "cached" in out


# ---------------------------------------------------------------------------
# cache status — partial and absent
# ---------------------------------------------------------------------------


def test_cache_status_absent_when_no_manifest(tmp_path: Path) -> None:
    """status returns 'absent' when no manifest exists."""
    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients)
    result = cache.status("flash", _REVISION, bucket=_BUCKET, prefix=_PREFIX)
    assert result == "absent"


def test_cache_status_partial_when_size_mismatch(tmp_path: Path) -> None:
    """status returns 'partial' when a file size doesn't match the manifest."""
    file_data = b"fake weights"
    manifest = {
        "model": "flash",
        "revision": _REVISION,
        "files": [
            {
                "path": "config.json",
                "size": len(file_data) + 100,  # wrong size
                "sha256": _sha256(file_data),
            }
        ],
        "total_bytes": len(file_data),
    }
    manifest_bytes = json.dumps(manifest).encode()
    existing_objects = {
        f"models/flash/{_REVISION}/config.json": file_data,
        f"models/flash/{_REVISION}/manifest.json": manifest_bytes,
    }
    s3 = _make_s3_client(objects=existing_objects)
    cfn = _make_cfn_client(cache_stack_exists=True)
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients)
    result = cache.status("flash", _REVISION, bucket=_BUCKET, prefix=_PREFIX)
    assert result == "partial"


def test_cache_status_complete_when_all_match(tmp_path: Path) -> None:
    """status returns 'complete' when manifest exists and all files match."""
    file_data = b"fake weights"
    manifest = {
        "model": "flash",
        "revision": _REVISION,
        "files": [
            {
                "path": "config.json",
                "size": len(file_data),
                "sha256": _sha256(file_data),
            }
        ],
        "total_bytes": len(file_data),
    }
    manifest_bytes = json.dumps(manifest).encode()
    existing_objects = {
        f"models/flash/{_REVISION}/config.json": file_data,
        f"models/flash/{_REVISION}/manifest.json": manifest_bytes,
    }
    s3 = _make_s3_client(objects=existing_objects)
    cfn = _make_cfn_client(cache_stack_exists=True)
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients)
    result = cache.status("flash", _REVISION, bucket=_BUCKET, prefix=_PREFIX)
    assert result == "complete"


# ---------------------------------------------------------------------------
# cache rm — refused while a deployment uses it
# ---------------------------------------------------------------------------


def test_cache_rm_refused_while_deployment_uses_it() -> None:
    """cache rm exits 3 when an ember-* stack's config points at the cache."""
    from ember_aws.model_cache import CacheInUseError

    # Simulate a deployment stack that references this bucket
    deployment_stacks = [
        {
            "StackName": "ember-default",
            "StackStatus": "CREATE_COMPLETE",
        }
    ]
    cfn = _make_cfn_client(cache_stack_exists=True, deployment_stacks=deployment_stacks)

    # SSM returns a config pointing at this bucket
    ssm = MagicMock()
    ssm.get_parameter.return_value = {
        "Parameter": {
            "Value": json.dumps(
                {
                    "ember_version": "0.12.0",
                    "model_s3_uri": f"s3://{_BUCKET}/models/flash/{_REVISION}",
                    "max_request_length": 24576,
                    "idle_minutes": 0,
                    "generation": 1,
                }
            )
        }
    }

    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)
    clients.ssm = ssm

    cache = ModelCache(clients=clients)
    with pytest.raises(CacheInUseError):
        cache.remove("flash", _REVISION, bucket=_BUCKET, prefix=_PREFIX)


def test_cache_rm_allowed_when_deployment_uses_other_revision() -> None:
    """cache rm succeeds when the deployment's config points at another revision."""
    deployment_stacks = [
        {
            "StackName": "ember-default",
            "StackStatus": "CREATE_COMPLETE",
        }
    ]
    cfn = _make_cfn_client(cache_stack_exists=True, deployment_stacks=deployment_stacks)

    ssm = MagicMock()
    ssm.get_parameter.return_value = {
        "Parameter": {
            "Value": json.dumps(
                {
                    "ember_version": "0.12.0",
                    "model_s3_uri": f"s3://{_BUCKET}/models/flash/other-revision",
                    "max_request_length": 24576,
                    "idle_minutes": 0,
                    "generation": 1,
                }
            )
        }
    }

    s3 = _make_s3_client()
    s3.list_objects_v2.return_value = {
        "Contents": [{"Key": f"models/flash/{_REVISION}/config.json"}],
        "IsTruncated": False,
    }
    clients = _make_aws_clients(s3=s3, cfn=cfn)
    clients.ssm = ssm

    cache = ModelCache(clients=clients)
    cache.remove("flash", _REVISION, bucket=_BUCKET, prefix=_PREFIX)

    assert s3.delete_object.called


def test_cache_rm_refused_when_config_unreadable() -> None:
    """cache rm fails closed when an active deployment's config cannot be read."""
    from botocore.exceptions import ClientError

    from ember_aws.model_cache import CacheInUseError

    deployment_stacks = [
        {
            "StackName": "ember-default",
            "StackStatus": "CREATE_COMPLETE",
        }
    ]
    cfn = _make_cfn_client(cache_stack_exists=True, deployment_stacks=deployment_stacks)

    ssm = MagicMock()
    ssm.get_parameter.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "throttled"}},
        "GetParameter",
    )

    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)
    clients.ssm = ssm

    cache = ModelCache(clients=clients)
    with pytest.raises(CacheInUseError):
        cache.remove("flash", _REVISION, bucket=_BUCKET, prefix=_PREFIX)


# ---------------------------------------------------------------------------
# cache destroy — requires --confirm and no deployments
# ---------------------------------------------------------------------------


def test_cache_destroy_requires_confirm() -> None:
    """cache destroy raises without --confirm <bucket>."""
    from ember_aws.model_cache import ConfirmationError

    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients)
    with pytest.raises(ConfirmationError):
        cache.destroy(confirm="wrong-bucket-name", bucket=_BUCKET)


def test_cache_destroy_refused_while_deployments_exist() -> None:
    """cache destroy exits 3 while any ember-* deployment stack exists."""
    from ember_aws.model_cache import CacheInUseError

    deployment_stacks = [
        {
            "StackName": "ember-default",
            "StackStatus": "CREATE_COMPLETE",
        }
    ]
    cfn = _make_cfn_client(cache_stack_exists=True, deployment_stacks=deployment_stacks)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients)
    with pytest.raises(CacheInUseError):
        cache.destroy(confirm=_BUCKET, bucket=_BUCKET)


def test_cache_destroy_refused_while_a_deploy_is_in_progress() -> None:
    """cache destroy fails closed while a deployment stack is in progress."""
    from ember_aws.model_cache import CacheInUseError

    deployment_stacks = [
        {"StackName": "ember-default", "StackStatus": "CREATE_IN_PROGRESS"}
    ]
    cfn = _make_cfn_client(cache_stack_exists=True)

    def list_stacks(StackStatusFilter: list[str]) -> dict[str, Any]:  # noqa: N803
        return {
            "StackSummaries": [
                s for s in deployment_stacks if s["StackStatus"] in StackStatusFilter
            ]
        }

    cfn.list_stacks.side_effect = list_stacks
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients)
    with pytest.raises(CacheInUseError):
        cache.destroy(confirm=_BUCKET, bucket=_BUCKET)


def test_cache_destroy_refused_before_a_deploy_stack_exists() -> None:
    """cache destroy fails closed on a deploy intent without a stack."""
    from ember_aws.model_cache import CacheInUseError

    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Parameters": [{"Name": "/ember/default/config", "Value": "{}"}]}
    ]
    clients.ssm.get_paginator.return_value = paginator

    cache = ModelCache(clients=clients)
    with pytest.raises(CacheInUseError):
        cache.destroy(confirm=_BUCKET, bucket=_BUCKET)


def test_cache_destroy_deletes_the_bucket_and_waits_for_the_stack() -> None:
    """destroy() empties and deletes the bucket, then the stack, and waits."""
    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "models/flash/rev/manifest.json"}],
        "IsTruncated": False,
    }
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients)
    cache.destroy(confirm=_BUCKET, bucket=None)

    s3.delete_object.assert_called_once()
    s3.delete_bucket.assert_called_once_with(Bucket=_BUCKET)
    cfn.delete_stack.assert_called_once_with(StackName="ember-model-cache")
    cfn.get_waiter.return_value.wait.assert_called_once_with(
        StackName="ember-model-cache"
    )


def test_cache_destroy_with_explicit_bucket_keeps_the_managed_stack() -> None:
    """destroy() with --bucket deletes that bucket, never the managed stack."""
    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients)
    cache.destroy(confirm=_BUCKET, bucket=_BUCKET)

    s3.delete_bucket.assert_called_once_with(Bucket=_BUCKET)
    cfn.delete_stack.assert_not_called()


# ---------------------------------------------------------------------------
# cache list — partial uploads, sizes, and deployments
# ---------------------------------------------------------------------------


def test_cache_list_shows_partial_prefixes_without_a_manifest() -> None:
    """A prefix with objects but no manifest lists as partial, not absent."""
    cfn = _make_cfn_client(cache_stack_exists=True)
    s3 = _make_s3_client()
    s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "models/flash/revX/model.safetensors"}],
        "IsTruncated": False,
    }
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients)
    results = cache.list(bucket=_BUCKET, prefix=_PREFIX)

    assert len(results) == 1
    assert results[0]["model"] == "flash"
    assert results[0]["revision"] == "revX"
    assert results[0]["status"] == "partial"


def test_cache_list_includes_size_and_deployments() -> None:
    """Each entry carries the manifest's total_bytes and the deployments using it."""
    manifest = {
        "model": "flash",
        "revision": "revX",
        "files": [],
        "total_bytes": 18 * 2**30,
    }
    manifest_bytes = json.dumps(manifest).encode()
    objects = {"models/flash/revX/manifest.json": manifest_bytes}
    cfn = _make_cfn_client(
        cache_stack_exists=True,
        deployment_stacks=[
            {"StackName": "ember-default", "StackStatus": "CREATE_COMPLETE"}
        ],
    )
    s3 = _make_s3_client(objects=objects)
    s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "models/flash/revX/manifest.json"},
            {"Key": "models/flash/revX/model.safetensors"},
        ],
        "IsTruncated": False,
    }
    ssm = MagicMock()
    ssm.get_parameter.return_value = {
        "Parameter": {
            "Value": json.dumps(
                {
                    "ember_version": "0.12.0",
                    "model_s3_uri": f"s3://{_BUCKET}/models/flash/revX",
                    "max_request_length": 24576,
                    "idle_minutes": 0,
                    "generation": 1,
                }
            )
        }
    }
    clients = _make_aws_clients(s3=s3, cfn=cfn)
    clients.ssm = ssm

    cache = ModelCache(clients=clients)
    results = cache.list(bucket=_BUCKET, prefix=_PREFIX)

    assert results[0]["total_bytes"] == 18 * 2**30
    assert results[0]["deployments"] == ["default"]


# ---------------------------------------------------------------------------
# --bucket/--prefix skips stack creation
# ---------------------------------------------------------------------------


def test_cache_add_with_explicit_bucket_skips_stack(tmp_path: Path) -> None:
    """Passing --bucket/--prefix skips stack creation entirely."""
    file_data = b"fake weights"
    files = {"config.json": file_data}
    downloader = _make_fake_downloader(tmp_path, files)
    cfn = _make_cfn_client(cache_stack_exists=False)
    s3 = _make_s3_client()
    clients = _make_aws_clients(s3=s3, cfn=cfn)

    cache = ModelCache(clients=clients, downloader=downloader)
    # Pass explicit bucket and prefix — should not touch CFN
    cache.add("flash", bucket="my-custom-bucket", prefix="custom/prefix/")

    cfn.create_stack.assert_not_called()
    cfn.describe_stacks.assert_not_called()
