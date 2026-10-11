"""Guard logic for cache removal and destruction operations."""

from __future__ import annotations

import json
import sys
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
) -> None:
    """Raise CacheInUseError if any deployment uses this model.

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

    Raises
    ------
    CacheInUseError
        If a deployment stack's config references this bucket and model.
    """
    s3_uri_prefix = f"s3://{bucket}"
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
            config_json = resp["Parameter"]["Value"]
            config = json.loads(config_json)
            model_s3_uri: str = config.get("model_s3_uri", "")
            if model_s3_uri.startswith(s3_uri_prefix):
                raise CacheInUseError(
                    f"deployment {stack_name!r} uses this cache "
                    f"({model_s3_uri!r}); destroy the deployment first"
                )
        except CacheInUseError:
            raise
        except Exception as exc:  # unreadable config must not block the guard
            print(f"warning: cannot read {param_name}: {exc}", file=sys.stderr)
