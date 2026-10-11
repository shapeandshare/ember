"""Read the current parameter values of a CloudFormation stack."""

from __future__ import annotations

from typing import Any


def read(clients: Any, stack_name: str) -> dict[str, str]:
    """Return a stack's current parameter key → value mapping.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    stack_name : str
        CloudFormation stack name.

    Returns
    -------
    dict[str, str]
        The stack's ``Parameters`` as a plain mapping; empty when the stack
        is absent or reports none.
    """
    from botocore.exceptions import ClientError  # import-placement:allow

    try:
        resp = clients.cfn.describe_stacks(StackName=stack_name)
    except ClientError:
        return {}
    stacks = resp.get("Stacks", [])
    if not stacks:
        return {}
    parameters: list[dict[str, str]] = stacks[0].get("Parameters", [])
    return {p["ParameterKey"]: p["ParameterValue"] for p in parameters}
