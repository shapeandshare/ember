"""Unit tests for ember.cfg.s3: the generic S3 download primitives.

Used by ember.serving.hosted to download a model from an operator-supplied
EMBER_MODEL_S3_URI. No dependency on ember.models/ModelSpec/REGISTRY — these
are plain (bucket, prefix, dest, label) functions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from ember.cfg import s3


def _s3_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "s3_access_key_id": "AKIAFAKE",
        "s3_secret_access_key": "fakesecret",
        "s3_region": "us-east-1",
    }
    values.update(overrides)
    return values


def test_s3_client_uses_default_credential_chain_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On a hosting platform with an attached IAM role (e.g. Outerbounds,
    with Metaflow-managed S3 access), no static
    access key/secret is configured at all — boto3's own default credential
    chain (instance/container role, env vars, ~/.aws/credentials) must be
    allowed to supply credentials. s3_client() MUST NOT require
    EMBER_S3_ACCESS_KEY_ID/_SECRET_ACCESS_KEY; it must construct a
    client with no explicit credential kwargs at all in that case."""
    monkeypatch.setattr(s3.config, "resolve", lambda key: None)
    captured: dict[str, object] = {}

    class _FakeBoto3:
        @staticmethod
        def client(service: str, **kwargs: object) -> str:
            captured["service"] = service
            captured.update(kwargs)
            return "fake-client"

    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3())
    result = s3.s3_client()
    assert result == "fake-client"
    assert captured["service"] == "s3"
    assert "aws_access_key_id" not in captured
    assert "aws_secret_access_key" not in captured
    assert captured["region_name"] is None


def test_s3_client_constructs_boto3_client_with_configured_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = _s3_values()
    monkeypatch.setattr(s3.config, "resolve", lambda key: values.get(key))
    captured: dict[str, object] = {}

    class _FakeBoto3:
        @staticmethod
        def client(service: str, **kwargs: object) -> str:
            captured["service"] = service
            captured.update(kwargs)
            return "fake-client"

    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3())
    result = s3.s3_client()
    assert result == "fake-client"
    assert captured["service"] == "s3"
    assert "endpoint_url" not in captured
    assert captured["aws_access_key_id"] == "AKIAFAKE"
    assert captured["aws_secret_access_key"] == "fakesecret"
    assert captured["region_name"] == "us-east-1"


def test_s3_client_uses_default_credential_chain_when_only_one_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partially-configured pair (e.g. a leftover access key with no
    secret) must not be passed through half-explicit — boto3 would reject
    that combination confusingly. Treat it the same as fully unconfigured:
    fall back to the default credential chain entirely."""
    values = {"s3_access_key_id": "AKIAFAKE"}
    monkeypatch.setattr(s3.config, "resolve", lambda key: values.get(key))
    captured: dict[str, object] = {}

    class _FakeBoto3:
        @staticmethod
        def client(service: str, **kwargs: object) -> str:
            captured.update(kwargs)
            return "fake-client"

    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3())
    s3.s3_client()
    assert "aws_access_key_id" not in captured
    assert "aws_secret_access_key" not in captured


def test_s3_client_wraps_construction_failure_as_actionable_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """boto3.client() itself can raise (e.g. ValueError for a bad region)
    before any network call is made. This must also surface as RuntimeError,
    not propagate raw — same reasoning as the ClientError-during-download
    wrapping below."""
    values = _s3_values(s3_region="not-a-real-region")
    monkeypatch.setattr(s3.config, "resolve", lambda key: values.get(key))

    class _FakeBoto3:
        @staticmethod
        def client(service: str, **kwargs: object) -> str:
            raise ValueError("Invalid region: not-a-real-region")

    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3())
    with pytest.raises(
        RuntimeError,
        match=r"could not create an S3 client: Invalid region: not-a-real-region",
    ):
        s3.s3_client()


def test_download_prefix_raises_when_no_objects_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakePaginator:
        @staticmethod
        def paginate(**_kwargs: object) -> list[dict[str, object]]:
            return [{"Contents": []}]

    class _FakeClient:
        @staticmethod
        def get_paginator(_name: str) -> _FakePaginator:
            return _FakePaginator()

    monkeypatch.setattr(s3, "s3_client", lambda: _FakeClient())
    with pytest.raises(RuntimeError, match=r"no objects found"):
        s3.download_prefix("my-bucket", "clef-flash", tmp_path / "dest", "test")


def test_download_prefix_wraps_client_error_as_actionable_runtime_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A boto3 ClientError (wrong bucket, bad credentials, network failure
    during listing/download) must surface as the same clear, actionable
    RuntimeError format as every other model-pull failure — cli.main only
    catches RuntimeError/KeyError cleanly, so an unwrapped ClientError would
    print a raw traceback instead of `error: ...`."""
    from botocore.exceptions import ClientError

    class _FakePaginator:
        @staticmethod
        def paginate(**_kwargs: object) -> None:
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "bucket not found"}},
                "ListObjectsV2",
            )

    class _FakeClient:
        @staticmethod
        def get_paginator(_name: str) -> _FakePaginator:
            return _FakePaginator()

    monkeypatch.setattr(s3, "s3_client", lambda: _FakeClient())
    with pytest.raises(RuntimeError, match=r"NoSuchBucket|bucket not found"):
        s3.download_prefix("my-bucket", "clef-flash", tmp_path / "dest", "test")


def test_download_prefix_downloads_every_object_under_the_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    downloaded: list[tuple[str, str, str]] = []

    class _FakePaginator:
        @staticmethod
        def paginate(**_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "Contents": [
                        # A zero-byte "directory marker" object (key exactly
                        # equal to the prefix + "/"), common in S3
                        # UIs/uploaders — must be skipped, not downloaded as a
                        # file named "" under dest.
                        {"Key": "clef-flash/"},
                        {"Key": "clef-flash/config.json"},
                        {"Key": "clef-flash/subdir/joint_head.safetensors"},
                    ]
                }
            ]

    class _FakeClient:
        @staticmethod
        def get_paginator(_name: str) -> _FakePaginator:
            return _FakePaginator()

        @staticmethod
        def download_file(bucket: str, key: str, target: str) -> None:
            downloaded.append((bucket, key, target))
            Path(target).write_bytes(b"x")

    monkeypatch.setattr(s3, "s3_client", lambda: _FakeClient())
    dest = tmp_path / "dest"
    result = s3.download_prefix("my-bucket", "clef-flash", dest, "test")
    assert result == dest
    assert (result / "config.json").is_file()
    assert (result / "subdir" / "joint_head.safetensors").is_file()
    assert len(downloaded) == 2
    assert all(bucket == "my-bucket" for bucket, _key, _target in downloaded)


def test_download_prefix_normalizes_trailing_slash_on_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_prefix: list[str] = []

    class _FakePaginator:
        @staticmethod
        def paginate(**kwargs: object) -> list[dict[str, object]]:
            captured_prefix.append(str(kwargs["Prefix"]))
            return [{"Contents": []}]

    class _FakeClient:
        @staticmethod
        def get_paginator(_name: str) -> _FakePaginator:
            return _FakePaginator()

    monkeypatch.setattr(s3, "s3_client", lambda: _FakeClient())
    with pytest.raises(RuntimeError, match=r"no objects found"):
        s3.download_prefix("my-bucket", "clef-flash/", tmp_path / "dest", "test")
    assert captured_prefix == ["clef-flash/"]


# ###########################################################################
# D-006: S3 download must reject prefixes that exceed the size cap
# ###########################################################################
def test_download_prefix_raises_when_total_size_exceeds_max_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-006: download_prefix() must preflight the S3 prefix size and raise
    RuntimeError before downloading anything when it exceeds max_bytes."""

    class _FakePaginator:
        @staticmethod
        def paginate(**_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "Contents": [
                        {"Key": "model/config.json", "Size": 600 * 1024 * 1024},
                    ]
                }
            ]

    class _FakeClient:
        @staticmethod
        def get_paginator(_name: str) -> _FakePaginator:
            return _FakePaginator()

        @staticmethod
        def download_file(bucket: str, key: str, target: str) -> None:
            raise AssertionError(
                "download_file must not be called when size exceeds cap"
            )

    monkeypatch.setattr(s3, "s3_client", lambda: _FakeClient())
    with pytest.raises(RuntimeError, match=r"exceeds|too large|max"):
        s3.download_prefix(
            "my-bucket",
            "model",
            tmp_path / "dest",
            "test",
            max_bytes=500 * 1024 * 1024,
        )


def test_download_prefix_proceeds_when_size_within_max_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-006: download_prefix() must download normally when size is within cap."""
    downloaded: list[str] = []

    class _FakePaginator:
        @staticmethod
        def paginate(**_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "Contents": [
                        {"Key": "model/config.json", "Size": 100},
                    ]
                }
            ]

    class _FakeClient:
        @staticmethod
        def get_paginator(_name: str) -> _FakePaginator:
            return _FakePaginator()

        @staticmethod
        def download_file(bucket: str, key: str, target: str) -> None:
            downloaded.append(key)
            Path(target).write_bytes(b"x")

    monkeypatch.setattr(s3, "s3_client", lambda: _FakeClient())
    s3.download_prefix(
        "my-bucket",
        "model",
        tmp_path / "dest",
        "test",
        max_bytes=500 * 1024 * 1024,
    )
    assert len(downloaded) == 1


def test_download_prefix_no_cap_when_max_bytes_is_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-006: max_bytes=0 disables the size preflight entirely."""
    downloaded: list[str] = []

    class _FakePaginator:
        @staticmethod
        def paginate(**_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "Contents": [
                        {"Key": "model/config.json", "Size": 999 * 1024 * 1024 * 1024},
                    ]
                }
            ]

    class _FakeClient:
        @staticmethod
        def get_paginator(_name: str) -> _FakePaginator:
            return _FakePaginator()

        @staticmethod
        def download_file(bucket: str, key: str, target: str) -> None:
            downloaded.append(key)
            Path(target).write_bytes(b"x")

    monkeypatch.setattr(s3, "s3_client", lambda: _FakeClient())
    s3.download_prefix(
        "my-bucket",
        "model",
        tmp_path / "dest",
        "test",
        max_bytes=0,
    )
    assert len(downloaded) == 1
