"""Tests for Preflight and CheckResult (T018)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ember_aws.check_result import CheckResult
from ember_aws.deployment import Deployment
from ember_aws.names import DeploymentName
from ember_aws.preflight import Preflight
from ember_aws.preflight_check import PreflightCheck

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deployment(instance_type: str = "g6e.xlarge") -> Deployment:
    return Deployment(name="default", model="flash", instance_type=instance_type)


def _make_names() -> DeploymentName:
    return DeploymentName(name="default")


def _make_sts_client(account_id: str = "123456789012") -> Any:
    """Return a mock STS client that returns a valid identity."""
    sts = MagicMock()
    sts.get_caller_identity.return_value = {
        "Account": account_id,
        "Arn": f"arn:aws:iam::{account_id}:user/test",
        "UserId": "AIDATEST",
    }
    return sts


def _make_quotas_client(vcpu_value: float = 192.0) -> Any:
    """Return a mock Service Quotas client."""
    quotas = MagicMock()
    quotas.get_service_quota.return_value = {
        "Quota": {
            "QuotaCode": "L-DB2E81BA",
            "Value": vcpu_value,
        }
    }
    return quotas


def _make_ec2_client(offered_types: list[str] | None = None) -> Any:
    """Return a mock EC2 client that reports instance type offerings."""
    if offered_types is None:
        offered_types = ["g6e.xlarge"]
    ec2 = MagicMock()

    def describe_instance_type_offerings(
        LocationType: str = "availability-zone",  # noqa: N803
        Filters: list[dict[str, object]] | None = None,  # noqa: N803
        **kwargs: object,
    ) -> dict[str, object]:
        # Filter by instance-type if a Filters list is provided.
        types_to_return = list(offered_types)
        if Filters:
            for f in Filters:
                if f.get("Name") == "instance-type":
                    allowed = set(f.get("Values", []))
                    types_to_return = [t for t in types_to_return if t in allowed]
        return {
            "InstanceTypeOfferings": [
                {
                    "InstanceType": t,
                    "LocationType": "availability-zone",
                    "Location": "us-east-1a",
                }
                for t in types_to_return
            ]
        }

    ec2.describe_instance_type_offerings.side_effect = describe_instance_type_offerings
    ec2.describe_availability_zones.return_value = {
        "AvailabilityZones": [{"ZoneName": "us-east-1a", "State": "available"}]
    }
    return ec2


def _make_tailscale_client(
    *,
    magic_dns: bool = True,
    suffix: str = "example.ts.net",
    tag_error: bool = False,
) -> Any:
    """Return a mock TailscaleClient."""
    ts = MagicMock()
    ts.tailnet_dns.return_value = {"magic_dns": magic_dns, "suffix": suffix}
    if tag_error:
        from ember_aws.tailscale_client import TailscaleError

        ts.mint_join_key.side_effect = TailscaleError(
            "requested tags are invalid or not permitted"
        )
    else:
        ts.mint_join_key.return_value = {"id": "key-test", "key": "tskey-auth-test"}
    ts.delete_key.return_value = None
    return ts


def _make_aws_clients(
    sts: Any = None,
    quotas: Any = None,
    ec2: Any = None,
) -> Any:
    """Bundle mock AWS clients."""
    clients = MagicMock()
    clients.sts = sts or _make_sts_client()
    clients.quotas = quotas or _make_quotas_client()
    clients.ec2 = ec2 or _make_ec2_client()
    return clients


# ---------------------------------------------------------------------------
# CheckResult model
# ---------------------------------------------------------------------------


def test_check_result_ok() -> None:
    """CheckResult with ok=True has no problem or fix."""
    result = CheckResult(
        check=PreflightCheck.AWS_IDENTITY,
        ok=True,
        problem="",
        fix="",
        blocking=True,
    )
    assert result.ok is True
    assert result.check == PreflightCheck.AWS_IDENTITY


def test_check_result_failing() -> None:
    """CheckResult with ok=False carries problem and fix."""
    result = CheckResult(
        check=PreflightCheck.GPU_QUOTA,
        ok=False,
        problem="quota too low",
        fix="request more vCPUs",
        blocking=True,
    )
    assert result.ok is False
    assert "quota" in result.problem
    assert "vCPU" in result.fix


def test_tailscale_https_is_non_blocking() -> None:
    """tailscale-https check is non-blocking by design."""
    result = CheckResult(
        check=PreflightCheck.TAILSCALE_HTTPS,
        ok=False,
        problem="cannot be checked before deploy",
        fix="confirm HTTPS Certificates is on",
        blocking=False,
    )
    assert result.blocking is False


# ---------------------------------------------------------------------------
# Preflight.run — happy path
# ---------------------------------------------------------------------------


def test_preflight_all_pass() -> None:
    """All checks pass → list of CheckResult all ok=True (except https notice)."""
    clients = _make_aws_clients()
    ts = _make_tailscale_client()
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    results = pf.run(_make_deployment())

    blocking_failures = [r for r in results if not r.ok and r.blocking]
    assert blocking_failures == [], blocking_failures


# ---------------------------------------------------------------------------
# Preflight.run — individual failures
# ---------------------------------------------------------------------------


def test_preflight_missing_credentials_fails() -> None:
    """Missing AWS credentials → aws-identity check fails with fix hint."""
    from botocore.exceptions import NoCredentialsError

    clients = _make_aws_clients()
    clients.sts.get_caller_identity.side_effect = NoCredentialsError()
    ts = _make_tailscale_client()
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    results = pf.run(_make_deployment())

    identity_result = next(r for r in results if r.check == PreflightCheck.AWS_IDENTITY)
    assert identity_result.ok is False
    assert (
        "aws sso login" in identity_result.fix or "AWS_PROFILE" in identity_result.fix
    )


def test_preflight_quota_too_low_fails() -> None:
    """GPU quota below instance vCPUs → gpu-quota check fails with quota link."""
    # g6e.xlarge has 4 vCPUs; set quota to 0
    clients = _make_aws_clients(quotas=_make_quotas_client(vcpu_value=0.0))
    ts = _make_tailscale_client()
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    results = pf.run(_make_deployment())

    quota_result = next(r for r in results if r.check == PreflightCheck.GPU_QUOTA)
    assert quota_result.ok is False
    # Fix should contain a link to the quota request page
    assert "quota" in quota_result.fix.lower() or "https://" in quota_result.fix


def test_preflight_instance_not_offered_fails() -> None:
    """Instance type not offered in region → instance-offering check fails."""
    clients = _make_aws_clients(ec2=_make_ec2_client(offered_types=["g5.2xlarge"]))
    ts = _make_tailscale_client()
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    results = pf.run(_make_deployment(instance_type="g6e.xlarge"))

    offering_result = next(
        r for r in results if r.check == PreflightCheck.INSTANCE_OFFERING
    )
    assert offering_result.ok is False


def test_preflight_missing_tailscale_env_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing TS_OAUTH_CLIENT_ID/SECRET → tailscale-oauth check fails."""
    monkeypatch.delenv("TS_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("TS_OAUTH_CLIENT_SECRET", raising=False)
    clients = _make_aws_clients()
    ts = MagicMock()
    ts.client_id = None
    ts.tailnet_dns.return_value = {"magic_dns": True, "suffix": "example.ts.net"}
    ts.mint_join_key.return_value = {"id": "key-test", "key": "tskey-auth-test"}
    ts.delete_key.return_value = None

    pf = Preflight(
        clients=clients,
        tailscale=None,  # type: ignore[arg-type]
        which=lambda _: "/usr/bin/tailscale",
    )
    results = pf.run(_make_deployment())

    oauth_result = next(r for r in results if r.check == PreflightCheck.TAILSCALE_OAUTH)
    assert oauth_result.ok is False


def test_preflight_tag_ownership_error_fails() -> None:
    """Tag ownership error → tailscale-tag check fails with tagOwners guidance."""
    clients = _make_aws_clients()
    ts = _make_tailscale_client(tag_error=True)
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    results = pf.run(_make_deployment())

    tag_result = next(r for r in results if r.check == PreflightCheck.TAILSCALE_TAG)
    assert tag_result.ok is False
    assert "tagOwners" in tag_result.fix or "tag" in tag_result.fix.lower()


def test_preflight_magicdns_off_fails() -> None:
    """MagicDNS disabled → tailscale-magicdns check fails."""
    clients = _make_aws_clients()
    ts = _make_tailscale_client(magic_dns=False)
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    results = pf.run(_make_deployment())

    dns_result = next(
        r for r in results if r.check == PreflightCheck.TAILSCALE_MAGICDNS
    )
    assert dns_result.ok is False


def test_preflight_missing_tailscale_tool_fails() -> None:
    """Missing tailscale CLI → tooling check fails."""
    clients = _make_aws_clients()
    ts = _make_tailscale_client()
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: None)
    results = pf.run(_make_deployment())

    tooling_result = next(r for r in results if r.check == PreflightCheck.TOOLING)
    assert tooling_result.ok is False


# ---------------------------------------------------------------------------
# HTTPS notice (non-blocking)
# ---------------------------------------------------------------------------


def test_preflight_https_notice_is_non_blocking() -> None:
    """tailscale-https always produces a non-blocking notice."""
    clients = _make_aws_clients()
    ts = _make_tailscale_client()
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    results = pf.run(_make_deployment())

    https_result = next(r for r in results if r.check == PreflightCheck.TAILSCALE_HTTPS)
    assert https_result.blocking is False
    # The notice text must mention HTTPS Certificates
    assert "HTTPS" in https_result.problem or "HTTPS" in https_result.fix


# ---------------------------------------------------------------------------
# No mutating AWS calls
# ---------------------------------------------------------------------------


def test_preflight_makes_no_mutating_aws_calls() -> None:
    """Preflight must not call any create/update/put/delete AWS API."""
    clients = _make_aws_clients()
    ts = _make_tailscale_client()
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    pf.run(_make_deployment())

    # Check that no mutating methods were called on any client
    for attr in ("cfn", "ec2", "ssm", "s3"):
        mock_client = getattr(clients, attr)
        for call in mock_client.method_calls:
            method_name = call[0].lower()
            for verb in ("create", "update", "put", "delete", "terminate", "run"):
                assert verb not in method_name, (
                    f"Preflight called mutating method {call[0]} on {attr}"
                )


def test_preflight_test_key_deleted_after_mint() -> None:
    """The test key minted during preflight is deleted immediately."""
    clients = _make_aws_clients()
    ts = _make_tailscale_client()
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    pf.run(_make_deployment())

    # mint_join_key was called once (for the test)
    ts.mint_join_key.assert_called_once()
    # delete_key was called with the returned key id
    ts.delete_key.assert_called_once_with("key-test")


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


def test_preflight_failure_line_format(capsys: pytest.CaptureFixture[str]) -> None:
    """Each failing check produces exactly one ✗ line with the right format."""
    from botocore.exceptions import NoCredentialsError

    clients = _make_aws_clients()
    clients.sts.get_caller_identity.side_effect = NoCredentialsError()
    ts = _make_tailscale_client()
    pf = Preflight(clients=clients, tailscale=ts, which=lambda _: "/usr/bin/tailscale")
    results = pf.run(_make_deployment())

    # Render the results as the CLI would
    lines = []
    for r in results:
        if not r.ok and r.blocking:
            lines.append(f"✗ {r.check}: {r.problem} — fix: {r.fix}")
        elif not r.ok and not r.blocking:
            lines.append(f"! {r.check}: {r.problem}")

    identity_lines = [line for line in lines if "aws-identity" in line]
    assert len(identity_lines) == 1
    assert identity_lines[0].startswith("✗ aws-identity:")
    assert "— fix:" in identity_lines[0]
