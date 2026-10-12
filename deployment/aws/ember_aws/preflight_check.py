"""PreflightCheck enum: checks run before any deployment change."""

from __future__ import annotations

from enum import StrEnum


class PreflightCheck(StrEnum):
    """Individual check performed by the preflight command.

    Attributes
    ----------
    AWS_IDENTITY : str
        AWS credentials are valid and an identity can be retrieved.
    REGION : str
        The target region is accessible.
    TOOLING : str
        Required local tools (tailscale CLI) are present.
    GPU_QUOTA : str
        Service quota for G/VT on-demand vCPUs is sufficient.
    INSTANCE_OFFERING : str
        The requested instance type is offered in the target region.
    TAILSCALE_OAUTH : str
        Tailscale OAuth client credentials are present in the environment.
    TAILSCALE_TAG : str
        The Tailscale tag is owned by the OAuth client.
    TAILSCALE_MAGICDNS : str
        MagicDNS is enabled on the tailnet.
    TAILSCALE_HTTPS : str
        HTTPS certificates are enabled (non-blocking; cannot be verified pre-deploy).
    MODEL_CACHED : str
        The model revision is present in the S3 cache.
    """

    AWS_IDENTITY = "aws-identity"
    REGION = "region"
    TOOLING = "tooling"
    GPU_QUOTA = "gpu-quota"
    INSTANCE_OFFERING = "instance-offering"
    TAILSCALE_OAUTH = "tailscale-oauth"
    TAILSCALE_TAG = "tailscale-tag"
    TAILSCALE_MAGICDNS = "tailscale-magicdns"
    TAILSCALE_HTTPS = "tailscale-https"
    MODEL_CACHED = "model-cached"
