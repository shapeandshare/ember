"""Guard logic for cache removal and destruction operations."""

from __future__ import annotations

import json
from typing import Any

#: The CloudFormation stack name for the shared model cache.
_CACHE_STACK_NAME = "ember-model-cache"

#: Every non-deleted CloudFormation stack status.
_LIVE_STACK_STATUSES = [
    "CREATE_IN_PROGRESS",
    "CREATE_FAILED",
    "CREATE_COMPLETE",
    "ROLLBACK_IN_PROGRESS",
    "ROLLBACK_FAILED",
    "ROLLBACK_COMPLETE",
    "DELETE_IN_PROGRESS",
    "DELETE_FAILED",
    "UPDATE_IN_PROGRESS",
    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
    "UPDATE_COMPLETE",
    "UPDATE_FAILED",
    "UPDATE_ROLLBACK_IN_PROGRESS",
    "UPDATE_ROLLBACK_FAILED",
    "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
    "UPDATE_ROLLBACK_COMPLETE",
    "REVIEW_IN_PROGRESS",
    "IMPORT_IN_PROGRESS",
    "IMPORT_COMPLETE",
    "IMPORT_ROLLBACK_IN_PROGRESS",
    "IMPORT_ROLLBACK_FAILED",
    "IMPORT_ROLLBACK_COMPLETE",
]


def _raise_in_use(name: str) -> None:
    """Raise CacheInUseError naming the deployment that uses the cache.

    Parameters
    ----------
    name : str
        Deployment name.

    Raises
    ------
    CacheInUseError
        Always.
    """
    raise CacheInUseError(
        f"deployment {name!r} exists; destroy it first with `make aws-down NAME={name}`"
    )


def _live_stacks(clients: Any) -> list[dict[str, Any]]:
    """Return every non-deleted stack summary, following pagination.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).

    Returns
    -------
    list[dict[str, Any]]
        Stack summaries.  ``list_stacks`` returns one page at a time, so a
        deployment on a later page must still be seen by the guards.
    """
    paginator = clients.cfn.get_paginator("list_stacks")
    summaries: list[dict[str, Any]] = []
    for page in paginator.paginate(StackStatusFilter=_LIVE_STACK_STATUSES):
        summaries.extend(page.get("StackSummaries", []))
    return summaries


def check_no_deployments(clients: Any) -> None:
    """Raise CacheInUseError if any deployment exists or is being prepared.

    A deploy writes its SSM config before creating its stack, so scanning
    both non-deleted stacks and ``/ember/*/config`` parameters covers the
    pre-stack window and every in-progress state.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).

    Raises
    ------
    CacheInUseError
        If any deployment stack exists in a non-deleted state, or any
        ``/ember/*/config`` deployment-intent parameter exists.
    """
    stacks = _live_stacks(clients)
    for stack_summary in stacks:
        stack_name = stack_summary.get("StackName", "")
        if stack_name.startswith("ember-") and stack_name != _CACHE_STACK_NAME:
            _raise_in_use(stack_name[len("ember-") :])
    paginator = clients.ssm.get_paginator("get_parameters_by_path")
    for page in paginator.paginate(Path="/ember", Recursive=True):
        for param in page.get("Parameters", []):
            name = param.get("Name", "")
            if name.endswith("/config"):
                _raise_in_use(name.split("/")[-2])


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
    for stack_summary in _live_stacks(clients):
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
