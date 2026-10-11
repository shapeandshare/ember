"""Guard logic for cache removal and destruction operations."""

from __future__ import annotations

import json
from typing import Any

#: The CloudFormation stack name for the shared model cache.
_CACHE_STACK_NAME = "ember-model-cache"


class CacheInUseError(Exception):
    """Raised when a cache removal is refused because a deployment uses it.

    Parameters
    ----------
    message : str
        Human-readable description of which deployment is using the cache.
    """


class ConfirmationError(Exception):
    """Raised when a destructive operation is attempted without confirmation.

    Parameters
    ----------
    message : str
        Human-readable description of the required confirmation.
    """


def check_not_in_use(
    clients: Any,
    bucket: str,
    model: str,
    revision: str,
    prefix: str = "models/",
) -> None:
    """Raise CacheInUseError if any deployment uses this model revision.

    Matches the exact, normalized ``s3://<bucket>/<prefix><model>/<revision>``
    URI against each active deployment's configured ``model_s3_uri``, so
    removing an unused revision is allowed while any deployment exists.
    Unreadable deployment configs fail closed: the cache may be in use, so
    removal is refused rather than risked.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    bucket : str
        S3 bucket name.
    model : str
        Registry key.
    revision : str
        Model revision.
    prefix : str
        S3 key prefix; defaults to ``"models/"``.

    Raises
    ------
    CacheInUseError
        If a deployment stack's config references this exact model revision,
        or if an active deployment's config cannot be read.
    """
    expected_uri = f"s3://{bucket}/{prefix}{model}/{revision}".rstrip("/")
    _active = ["CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"]
    stacks = clients.cfn.list_stacks(StackStatusFilter=_active)
    for stack_summary in stacks.get("StackSummaries", []):
        stack_name = stack_summary.get("StackName", "")
        if not stack_name.startswith("ember-") or stack_name == _CACHE_STACK_NAME:
            continue
        deployment_name = stack_name[len("ember-") :]
        param_name = f"/ember/{deployment_name}/config"
        try:
            resp = clients.ssm.get_parameter(Name=param_name)
            config = json.loads(resp["Parameter"]["Value"])
        except Exception as exc:
            raise CacheInUseError(
                f"cannot read {stack_name!r} config ({param_name}): {exc}; "
                "refusing to remove a cache that may be in use"
            ) from exc
        model_s3_uri = str(config.get("model_s3_uri", "")).rstrip("/")
        if model_s3_uri == expected_uri:
            raise CacheInUseError(
                f"deployment {stack_name!r} uses this cache "
                f"({model_s3_uri!r}); destroy the deployment first"
            )
