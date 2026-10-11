"""AwsClients: a single boto3 session exposing all service clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import boto3


@dataclass(frozen=True)
class AwsClients:
    """A frozen bundle of boto3 service clients built from one session.

    This is the single seam that tests replace with stubbed clients.
    Construct via :meth:`from_region` or inject directly in tests.

    Parameters
    ----------
    cfn : Any
        CloudFormation client (``boto3.client("cloudformation")``).
    ec2 : Any
        EC2 client (``boto3.client("ec2")``).
    ssm : Any
        SSM Parameter Store client (``boto3.client("ssm")``).
    s3 : Any
        S3 client (``boto3.client("s3")``).
    sts : Any
        STS client (``boto3.client("sts")``).
    quotas : Any
        Service Quotas client (``boto3.client("service-quotas")``).
    """

    cfn: Any
    ec2: Any
    ssm: Any
    s3: Any
    sts: Any
    quotas: Any

    @classmethod
    def from_region(cls, region: str) -> AwsClients:
        """Build all clients from a single boto3 session for the given region.

        Parameters
        ----------
        region : str
            AWS region name (e.g. ``"us-east-1"``).

        Returns
        -------
        AwsClients
            A frozen bundle of service clients sharing one session.
        """
        session = boto3.Session(region_name=region)
        return cls(
            cfn=session.client("cloudformation"),
            ec2=session.client("ec2"),
            ssm=session.client("ssm"),
            s3=session.client("s3"),
            sts=session.client("sts"),
            quotas=session.client("service-quotas"),
        )
