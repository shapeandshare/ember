"""Preflight: read-only checks before any deployment change."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from typing import Any

from .capacity import Capacity
from .check_result import CheckResult
from .deployment import Deployment
from .preflight_check import PreflightCheck
from .tailscale_client import TailscaleClient, TailscaleError

#: vCPU count for each instance type we care about.
_INSTANCE_VCPUS: dict[str, int] = {
    "g6e.xlarge": 4,
    "g5.2xlarge": 8,
    "g5.4xlarge": 16,
    "g4dn.xlarge": 4,
    "g4dn.2xlarge": 8,
    "p3.2xlarge": 8,
    "p4d.24xlarge": 96,
    "p5.48xlarge": 192,
}

#: Service Quotas quota codes for G and VT vCPUs, per capacity.
_GPU_QUOTA_CODE = "L-DB2E81BA"
_GPU_QUOTA_CODE_SPOT = "L-3819A6DF"
_GPU_QUOTA_SERVICE = "ec2"


class Preflight:
    """Read-only preflight checks before any deployment change.

    Runs every :class:`~ember_aws.preflight_check.PreflightCheck` and returns
    a list of :class:`~ember_aws.check_result.CheckResult` objects.  The only
    mutating Tailscale call is minting and immediately deleting a test key to
    verify tag ownership.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    tailscale : TailscaleClient | None
        A configured Tailscale client, or ``None`` when the OAuth env vars are
        absent (the ``tailscale-oauth`` check will fail).
    which : Callable[[str], str | None]
        A callable with the same signature as :func:`shutil.which`; injected
        for testing.
    """

    def __init__(
        self,
        clients: Any,
        tailscale: TailscaleClient | None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._clients = clients
        self._tailscale = tailscale
        self._which = which

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, deployment: Deployment) -> list[CheckResult]:
        """Run all preflight checks for the given deployment.

        Parameters
        ----------
        deployment : Deployment
            The desired deployment state to validate.

        Returns
        -------
        list[CheckResult]
            One result per :class:`~ember_aws.preflight_check.PreflightCheck`,
            in definition order.
        """
        results: list[CheckResult] = []
        results.append(self._check_aws_identity())
        results.append(self._check_region())
        results.append(self._check_tooling())
        results.append(self._check_gpu_quota(deployment))
        results.append(self._check_instance_offering(deployment))
        results.append(self._check_tailscale_oauth())
        results.append(self._check_tailscale_tag(deployment))
        results.append(self._check_tailscale_magicdns())
        results.append(self._check_tailscale_https())
        return results

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_aws_identity(self) -> CheckResult:
        """Verify AWS credentials are valid."""
        try:
            self._clients.sts.get_caller_identity()
            return CheckResult(
                check=PreflightCheck.AWS_IDENTITY,
                ok=True,
                problem="",
                fix="",
                blocking=True,
            )
        except Exception as exc:
            exc_str = str(exc).lower()
            if "credential" in exc_str or "token" in exc_str or "auth" in exc_str:
                fix = "run `aws sso login` or set AWS_PROFILE"
            else:
                fix = "run `aws sso login` or set AWS_PROFILE"
            return CheckResult(
                check=PreflightCheck.AWS_IDENTITY,
                ok=False,
                problem=f"cannot retrieve AWS identity: {exc}",
                fix=fix,
                blocking=True,
            )

    def _check_region(self) -> CheckResult:
        """Verify the target region is accessible."""
        try:
            self._clients.ec2.describe_availability_zones()
            return CheckResult(
                check=PreflightCheck.REGION,
                ok=True,
                problem="",
                fix="",
                blocking=True,
            )
        except Exception as exc:
            return CheckResult(
                check=PreflightCheck.REGION,
                ok=False,
                problem=f"region not accessible: {exc}",
                fix="check AWS_DEFAULT_REGION or --region",
                blocking=True,
            )

    def _check_tooling(self) -> CheckResult:
        """Verify required local tools are present."""
        path = self._which("tailscale")
        if path:
            return CheckResult(
                check=PreflightCheck.TOOLING,
                ok=True,
                problem="",
                fix="",
                blocking=True,
            )
        return CheckResult(
            check=PreflightCheck.TOOLING,
            ok=False,
            problem="tailscale CLI not found on PATH",
            fix="install tailscale: https://tailscale.com/download or `make aws-tools`",
            blocking=True,
        )

    def _check_gpu_quota(self, deployment: Deployment) -> CheckResult:
        """Verify the G/VT vCPU quota for the deployment's capacity is sufficient."""
        instance_type = deployment.instance_type or "g6e.xlarge"
        required_vcpus = _INSTANCE_VCPUS.get(instance_type, 4)
        spot = deployment.capacity == Capacity.SPOT
        quota_code = _GPU_QUOTA_CODE_SPOT if spot else _GPU_QUOTA_CODE
        quota_label = "G/VT Spot" if spot else "G/VT on-demand"
        quota_link = (
            "https://console.aws.amazon.com/servicequotas/home/services"
            f"/ec2/quotas/{quota_code}"
        )
        try:
            response = self._clients.quotas.get_service_quota(
                ServiceCode=_GPU_QUOTA_SERVICE,
                QuotaCode=quota_code,
            )
            quota_value = float(response["Quota"]["Value"])
            if quota_value >= required_vcpus:
                return CheckResult(
                    check=PreflightCheck.GPU_QUOTA,
                    ok=True,
                    problem="",
                    fix="",
                    blocking=True,
                )
            return CheckResult(
                check=PreflightCheck.GPU_QUOTA,
                ok=False,
                problem=(
                    f"{quota_label} vCPU quota is {quota_value:.0f},"
                    f" but {instance_type} needs {required_vcpus}"
                ),
                fix=f"request a quota increase: {quota_link}",
                blocking=True,
            )
        except Exception as exc:
            return CheckResult(
                check=PreflightCheck.GPU_QUOTA,
                ok=False,
                problem=f"cannot check GPU quota: {exc}",
                fix=f"request a quota increase: {quota_link}",
                blocking=True,
            )

    def _check_instance_offering(self, deployment: Deployment) -> CheckResult:
        """Verify the instance type is offered in the target region."""
        instance_type = deployment.instance_type or "g6e.xlarge"
        try:
            response = self._clients.ec2.describe_instance_type_offerings(
                LocationType="availability-zone",
                Filters=[{"Name": "instance-type", "Values": [instance_type]}],
            )
            offerings = response.get("InstanceTypeOfferings", [])
            if offerings:
                return CheckResult(
                    check=PreflightCheck.INSTANCE_OFFERING,
                    ok=True,
                    problem="",
                    fix="",
                    blocking=True,
                )
            zones_response = self._clients.ec2.describe_instance_type_offerings(
                LocationType="availability-zone",
            )
            all_zones = [
                o["Location"] for o in zones_response.get("InstanceTypeOfferings", [])
            ]
            zones_str = ", ".join(sorted(set(all_zones))) or "none"
            return CheckResult(
                check=PreflightCheck.INSTANCE_OFFERING,
                ok=False,
                problem=f"{instance_type!r} is not offered in this region",
                fix=(
                    f"available zones: {zones_str}; "
                    "choose a different instance type or region"
                ),
                blocking=True,
            )
        except Exception as exc:
            return CheckResult(
                check=PreflightCheck.INSTANCE_OFFERING,
                ok=False,
                problem=f"cannot check instance offerings: {exc}",
                fix="verify the instance type and region",
                blocking=True,
            )

    def _check_tailscale_oauth(self) -> CheckResult:
        """Verify Tailscale OAuth credentials are present."""
        if self._tailscale is None:
            return CheckResult(
                check=PreflightCheck.TAILSCALE_OAUTH,
                ok=False,
                problem="TS_OAUTH_CLIENT_ID and/or TS_OAUTH_CLIENT_SECRET are not set",
                fix=(
                    "set TS_OAUTH_CLIENT_ID and TS_OAUTH_CLIENT_SECRET. "
                    "Create an OAuth client at "
                    "https://login.tailscale.com/admin/settings/oauth "
                    "with scopes: Auth Keys (write), Devices > Core (write), "
                    "DNS (read). In the Tags field enter 'tag:ember' "
                    "(create that tag first at "
                    "https://login.tailscale.com/admin/acls/file under Tags, "
                    "or via Admin console -> Access Controls -> Tags -> Create tag, "
                    "name 'ember', owner = your admin user or group)"
                ),
                blocking=True,
            )
        try:
            self._tailscale.token()
            return CheckResult(
                check=PreflightCheck.TAILSCALE_OAUTH,
                ok=True,
                problem="",
                fix="",
                blocking=True,
            )
        except TailscaleError as exc:
            return CheckResult(
                check=PreflightCheck.TAILSCALE_OAUTH,
                ok=False,
                problem=f"Tailscale OAuth token exchange failed: {exc}",
                fix=(
                    "set TS_OAUTH_CLIENT_ID and TS_OAUTH_CLIENT_SECRET. "
                    "Create an OAuth client at "
                    "https://login.tailscale.com/admin/settings/oauth "
                    "with scopes: Auth Keys (write), Devices > Core (write), "
                    "DNS (read). In the Tags field enter 'tag:ember' "
                    "(create that tag first at "
                    "https://login.tailscale.com/admin/acls/file under Tags, "
                    "or via Admin console -> Access Controls -> Tags -> Create tag, "
                    "name 'ember', owner = your admin user or group)"
                ),
                blocking=True,
            )

    def _check_tailscale_tag(self, deployment: Deployment) -> CheckResult:
        """Verify the Tailscale tag is owned by the OAuth client."""
        if self._tailscale is None:
            return CheckResult(
                check=PreflightCheck.TAILSCALE_TAG,
                ok=False,
                problem="Tailscale client not configured",
                fix="set TS_OAUTH_CLIENT_ID and TS_OAUTH_CLIENT_SECRET",
                blocking=True,
            )
        tag = deployment.tailscale_tag
        try:
            key_info = self._tailscale.mint_join_key(tag, expiry_s=60)
            key_id = key_info.get("id", "")
            if key_id:
                self._tailscale.delete_key(key_id)
            return CheckResult(
                check=PreflightCheck.TAILSCALE_TAG,
                ok=True,
                problem="",
                fix="",
                blocking=True,
            )
        except TailscaleError as exc:
            return CheckResult(
                check=PreflightCheck.TAILSCALE_TAG,
                ok=False,
                problem=f"tag {tag!r} is not owned by this OAuth client: {exc}",
                fix=(
                    f"ensure {tag!r} exists and is owned by your OAuth client. "
                    "UI path: Admin console -> Access Controls -> Tags -> "
                    "Create tag, name 'ember', owner = your admin user or group. "
                    "ACL JSON path: add to tagOwners: "
                    f'"{tag}": ["autogroup:admin"] '
                    "(Admin console → Access Controls). "
                    "Then re-create the OAuth client with Tags = 'tag:ember'"
                ),
                blocking=True,
            )

    def _check_tailscale_magicdns(self) -> CheckResult:
        """Verify MagicDNS is enabled on the tailnet."""
        if self._tailscale is None:
            return CheckResult(
                check=PreflightCheck.TAILSCALE_MAGICDNS,
                ok=False,
                problem="Tailscale client not configured",
                fix="set TS_OAUTH_CLIENT_ID and TS_OAUTH_CLIENT_SECRET",
                blocking=True,
            )
        try:
            dns_info = self._tailscale.tailnet_dns()
            if dns_info.get("magic_dns"):
                return CheckResult(
                    check=PreflightCheck.TAILSCALE_MAGICDNS,
                    ok=True,
                    problem="",
                    fix="",
                    blocking=True,
                )
            return CheckResult(
                check=PreflightCheck.TAILSCALE_MAGICDNS,
                ok=False,
                problem="MagicDNS is disabled on this tailnet",
                fix=(
                    "enable MagicDNS in the Tailscale admin console "
                    "(DNS page → MagicDNS toggle)"
                ),
                blocking=True,
            )
        except TailscaleError as exc:
            return CheckResult(
                check=PreflightCheck.TAILSCALE_MAGICDNS,
                ok=False,
                problem=f"cannot check MagicDNS: {exc}",
                fix="verify Tailscale credentials and tailnet access",
                blocking=True,
            )

    def _check_tailscale_https(self) -> CheckResult:
        """Return a non-blocking notice about HTTPS certificates.

        The Tailscale public API does not expose whether HTTPS certificates
        are enabled, so this check always returns a non-blocking notice.
        """
        return CheckResult(
            check=PreflightCheck.TAILSCALE_HTTPS,
            ok=False,
            problem=(
                "cannot be checked before deploy — confirm "
                '"HTTPS Certificates" is on (admin console → DNS)'
            ),
            fix='enable "HTTPS Certificates" in the Tailscale admin console (DNS page)',
            blocking=False,
        )
