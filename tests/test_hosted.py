"""Tests for ember.serving.hosted: the EMBER_MODEL_S3_URI startup-time resolution.

Constitution Article V ("Model Loading"): ember supports any model that can
run under its loader contract. A platform (e.g. Outerbounds) supplies the
model's S3 location as a URI at start time, with no matching REGISTRY entry
required.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ember.cfg import s3
from ember.serving import hosted


def test_resolve_returns_none_when_no_uri_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normal REGISTRY-based path is untouched when EMBER_MODEL_S3_URI is
    absent — resolve() must be a clean no-op, not an error."""
    monkeypatch.delenv("EMBER_MODEL_S3_URI", raising=False)
    assert hosted.resolve() is None


def test_resolve_raises_on_malformed_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBER_MODEL_S3_URI", "not-an-s3-uri")
    with pytest.raises(RuntimeError, match=r"EMBER_MODEL_S3_URI.*s3://"):
        hosted.resolve()


def test_resolve_raises_on_uri_missing_a_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """s3://bucket with no path at all is rejected — a bucket root is never a
    valid single-model location."""
    monkeypatch.setenv("EMBER_MODEL_S3_URI", "s3://my-bucket")
    with pytest.raises(RuntimeError, match=r"EMBER_MODEL_S3_URI"):
        hosted.resolve()


def test_resolve_downloads_and_returns_dir_when_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBER_MODEL_S3_URI", "s3://my-bucket/clef-flash")
    monkeypatch.setattr(
        hosted.paths, "hosted_model_cache", lambda uri: tmp_path / "cache"
    )

    captured: dict[str, object] = {}

    def _fake_download_prefix(bucket: str, prefix: str, dest: Path, label: str) -> Path:
        captured["bucket"] = bucket
        captured["prefix"] = prefix
        captured["dest"] = dest
        captured["label"] = label
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "config.json").write_text("{}")
        return dest

    monkeypatch.setattr(s3, "download_prefix", _fake_download_prefix)

    result = hosted.resolve()

    assert result is not None
    assert result.model_dir == tmp_path / "cache"
    assert (result.model_dir / "config.json").is_file()
    assert captured["bucket"] == "my-bucket"
    assert captured["prefix"] == "clef-flash"
    assert "s3://my-bucket/clef-flash" in str(captured["label"])


def test_resolve_skips_download_when_already_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running resolve() against an already-downloaded URI must not
    re-download — same idempotent-pull behavior as the REGISTRY path."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "config.json").write_text("{}")
    monkeypatch.setenv("EMBER_MODEL_S3_URI", "s3://my-bucket/clef-flash")
    monkeypatch.setattr(hosted.paths, "hosted_model_cache", lambda uri: cache_dir)

    def _fail_if_called(*_args: object, **_kwargs: object) -> Path:
        raise AssertionError("download_prefix must not be called when already cached")

    monkeypatch.setattr(s3, "download_prefix", _fail_if_called)

    result = hosted.resolve()

    assert result is not None
    assert result.model_dir == cache_dir


def test_resolved_source_reports_the_uri(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "config.json").write_text("{}")
    monkeypatch.setenv("EMBER_MODEL_S3_URI", "s3://my-bucket/clef-flash")
    monkeypatch.setattr(hosted.paths, "hosted_model_cache", lambda uri: cache_dir)

    result = hosted.resolve()

    assert result is not None
    assert result.uri == "s3://my-bucket/clef-flash"
