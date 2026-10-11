"""Tests for Deployment and InstanceConfig models (T014)."""

from __future__ import annotations

import json

import pytest

# ---------------------------------------------------------------------------
# T014 — Deployment defaults and validation
# ---------------------------------------------------------------------------


def test_deployment_default_region() -> None:
    from ember_aws.deployment import Deployment

    d = Deployment(name="default", model="flash")
    assert d.region == "us-west-2"


def test_deployment_default_capacity_on_demand() -> None:
    from ember_aws.capacity import Capacity
    from ember_aws.deployment import Deployment

    d = Deployment(name="default", model="flash")
    assert d.capacity == Capacity.ON_DEMAND


def test_deployment_default_idle_minutes_zero() -> None:
    from ember_aws.deployment import Deployment

    d = Deployment(name="default", model="flash")
    assert d.idle_minutes == 0


def test_deployment_default_ember_version_from_pyproject() -> None:
    """ember_version defaults to the pyproject.toml version."""
    import re
    import tomllib
    from pathlib import Path

    from ember_aws.deployment import Deployment

    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    expected = data["project"]["version"]

    d = Deployment(name="default", model="flash")
    assert d.ember_version == expected
    assert re.match(r"^\d+\.\d+\.\d+$", d.ember_version)


def test_deployment_default_tailscale_tag() -> None:
    from ember_aws.deployment import Deployment

    d = Deployment(name="default", model="flash")
    assert d.tailscale_tag == "tag:ember"


def test_deployment_rejects_negative_idle_minutes() -> None:
    from pydantic import ValidationError

    from ember_aws.deployment import Deployment

    with pytest.raises(ValidationError):
        Deployment(name="default", model="flash", idle_minutes=-1)


def test_deployment_accepts_zero_idle_minutes() -> None:
    from ember_aws.deployment import Deployment

    d = Deployment(name="default", model="flash", idle_minutes=0)
    assert d.idle_minutes == 0


def test_deployment_accepts_positive_idle_minutes() -> None:
    from ember_aws.deployment import Deployment

    d = Deployment(name="default", model="flash", idle_minutes=30)
    assert d.idle_minutes == 30


def test_deployment_ember_version_must_match_semver() -> None:
    from pydantic import ValidationError

    from ember_aws.deployment import Deployment

    with pytest.raises(ValidationError):
        Deployment(name="default", model="flash", ember_version="not-a-version")


def test_deployment_ember_version_rejects_prerelease() -> None:
    from pydantic import ValidationError

    from ember_aws.deployment import Deployment

    with pytest.raises(ValidationError):
        Deployment(name="default", model="flash", ember_version="1.0.0-alpha")


def test_deployment_ember_version_accepts_valid() -> None:
    from ember_aws.deployment import Deployment

    d = Deployment(name="default", model="flash", ember_version="1.2.3")
    assert d.ember_version == "1.2.3"


# ---------------------------------------------------------------------------
# T014 — InstanceConfig JSON round-trip and validation
# ---------------------------------------------------------------------------


def test_instance_config_json_round_trip() -> None:
    from ember_aws.instance_config import InstanceConfig

    cfg = InstanceConfig(
        ember_version="0.12.0",
        model_s3_uri="s3://my-bucket/models/flash/abc123",
        max_request_length=24576,
        idle_minutes=0,
        generation=1,
    )
    raw = cfg.model_dump_json()
    restored = InstanceConfig.model_validate_json(raw)
    assert restored == cfg


def test_instance_config_model_s3_uri_must_start_with_s3() -> None:
    from pydantic import ValidationError

    from ember_aws.instance_config import InstanceConfig

    with pytest.raises(ValidationError):
        InstanceConfig(
            ember_version="0.12.0",
            model_s3_uri="https://bucket/models/flash/abc123",
            max_request_length=24576,
            idle_minutes=0,
            generation=1,
        )


def test_instance_config_model_s3_uri_must_end_with_revision() -> None:
    """model_s3_uri must end with /<revision> (no trailing slash)."""
    from pydantic import ValidationError

    from ember_aws.instance_config import InstanceConfig

    with pytest.raises(ValidationError):
        InstanceConfig(
            ember_version="0.12.0",
            model_s3_uri="s3://my-bucket/models/flash/",
            max_request_length=24576,
            idle_minutes=0,
            generation=1,
        )


def test_instance_config_max_request_length_must_be_positive() -> None:
    from pydantic import ValidationError

    from ember_aws.instance_config import InstanceConfig

    with pytest.raises(ValidationError):
        InstanceConfig(
            ember_version="0.12.0",
            model_s3_uri="s3://my-bucket/models/flash/abc123",
            max_request_length=0,
            idle_minutes=0,
            generation=1,
        )


def test_instance_config_max_request_length_rejects_negative() -> None:
    from pydantic import ValidationError

    from ember_aws.instance_config import InstanceConfig

    with pytest.raises(ValidationError):
        InstanceConfig(
            ember_version="0.12.0",
            model_s3_uri="s3://my-bucket/models/flash/abc123",
            max_request_length=-1,
            idle_minutes=0,
            generation=1,
        )


def test_instance_config_generation_field_present() -> None:
    from ember_aws.instance_config import InstanceConfig

    cfg = InstanceConfig(
        ember_version="0.12.0",
        model_s3_uri="s3://my-bucket/models/flash/abc123",
        max_request_length=24576,
        idle_minutes=0,
        generation=5,
    )
    assert cfg.generation == 5


def test_instance_config_json_contains_generation() -> None:
    from ember_aws.instance_config import InstanceConfig

    cfg = InstanceConfig(
        ember_version="0.12.0",
        model_s3_uri="s3://my-bucket/models/flash/abc123",
        max_request_length=24576,
        idle_minutes=0,
        generation=3,
    )
    data = json.loads(cfg.model_dump_json())
    assert data["generation"] == 3
