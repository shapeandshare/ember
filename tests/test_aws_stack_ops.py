"""Tests for Stack operations: create, wait, update, change-set, delete (T027 ext)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_clients(
    *,
    stack_exists: bool = True,
    stack_status: str = "CREATE_COMPLETE",
    stack_outputs: list[dict[str, Any]] | None = None,
) -> Any:
    clients = MagicMock()
    if stack_exists:
        clients.cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "StackName": "ember-default",
                    "StackStatus": stack_status,
                    "Outputs": stack_outputs
                    or [
                        {"OutputKey": "InstanceId", "OutputValue": "i-0001"},
                        {
                            "OutputKey": "RoleArn",
                            "OutputValue": "arn:aws:iam::123:role/r",
                        },
                    ],
                }
            ]
        }
    else:
        from botocore.exceptions import ClientError

        clients.cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
            "DescribeStacks",
        )
    clients.cfn.create_stack.return_value = {
        "StackId": "arn:aws:cfn:us-east-1:123:stack/ember-default/x"
    }
    clients.cfn.get_waiter.return_value = MagicMock()
    clients.cfn.describe_stack_events.return_value = {"StackEvents": []}
    clients.cfn.delete_stack.return_value = {}
    clients.cfn.create_change_set.return_value = {}
    clients.cfn.execute_change_set.return_value = {}
    clients.cfn.describe_change_set.return_value = {"Changes": []}
    return clients


def _make_stack(clients: Any) -> Any:
    from ember_aws.names import DeploymentName
    from ember_aws.stack import Stack

    names = DeploymentName(name="default")
    return Stack(clients=clients, names=names)


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestStackCreate:
    """Stack.create() calls cfn.create_stack with correct parameters."""

    def test_create_passes_stack_name(self) -> None:
        """create() passes the correct StackName to cfn.create_stack."""
        clients = _make_clients()
        stack = _make_stack(clients)
        stack.create(params={"_template_body": "<template>"}, tags=[])
        call_kwargs = clients.cfn.create_stack.call_args.kwargs
        assert call_kwargs["StackName"] == "ember-default"

    def test_create_passes_capability_named_iam(self) -> None:
        """create() acknowledges the template's named IAM resources.

        The template sets RoleName and InstanceProfileName, which requires
        CAPABILITY_NAMED_IAM — plain CAPABILITY_IAM fails the live API with
        InsufficientCapabilitiesException.
        """
        clients = _make_clients()
        stack = _make_stack(clients)
        stack.create(params={"_template_body": "<template>"}, tags=[])
        call_kwargs = clients.cfn.create_stack.call_args.kwargs
        assert "CAPABILITY_NAMED_IAM" in call_kwargs["Capabilities"]

    def test_create_passes_tags(self) -> None:
        """create() forwards the tags list to cfn.create_stack."""
        clients = _make_clients()
        stack = _make_stack(clients)
        tags = [{"Key": "ember:deployment", "Value": "default"}]
        stack.create(params={"_template_body": "<template>"}, tags=tags)
        call_kwargs = clients.cfn.create_stack.call_args.kwargs
        assert call_kwargs["Tags"] == tags

    def test_create_converts_params_to_cfn_format(self) -> None:
        """create() converts dict params to [{ParameterKey, ParameterValue}] format."""
        clients = _make_clients()
        stack = _make_stack(clients)
        stack.create(
            params={"InstanceType": "g6e.xlarge", "_template_body": ""},
            tags=[],
        )
        call_kwargs = clients.cfn.create_stack.call_args.kwargs
        cfn_params = call_kwargs["Parameters"]
        param_map = {p["ParameterKey"]: p["ParameterValue"] for p in cfn_params}
        assert param_map["InstanceType"] == "g6e.xlarge"

    def test_create_excludes_internal_keys_from_cfn_parameters(self) -> None:
        """create() must not send internal _-prefixed keys as CFN parameters.

        The live API rejects unknown parameters with "Parameters:
        [_template_body] do not exist in the template".
        """
        clients = _make_clients()
        stack = _make_stack(clients)
        stack.create(
            params={"InstanceType": "g6e.xlarge", "_template_body": "<template>"},
            tags=[],
        )
        call_kwargs = clients.cfn.create_stack.call_args.kwargs
        keys = [p["ParameterKey"] for p in call_kwargs["Parameters"]]
        assert "_template_body" not in keys

    def test_create_uses_template_body_from_params(self) -> None:
        """create() uses _template_body from params as the TemplateBody."""
        clients = _make_clients()
        stack = _make_stack(clients)
        body = "AWSTemplateFormatVersion: '2010-09-09'"
        stack.create(params={"_template_body": body}, tags=[])
        call_kwargs = clients.cfn.create_stack.call_args.kwargs
        assert call_kwargs["TemplateBody"] == body


# ---------------------------------------------------------------------------
# wait()
# ---------------------------------------------------------------------------


class TestStackWait:
    """Stack.wait() uses the correct waiter and raises StackWaitError on failure."""

    def test_wait_create_uses_stack_create_complete_waiter(self) -> None:
        """wait('create') requests the stack_create_complete waiter."""
        clients = _make_clients()
        stack = _make_stack(clients)
        stack.wait("create")
        clients.cfn.get_waiter.assert_called_once_with("stack_create_complete")

    def test_wait_update_uses_stack_update_complete_waiter(self) -> None:
        """wait('update') requests the stack_update_complete waiter."""
        clients = _make_clients()
        stack = _make_stack(clients)
        stack.wait("update")
        clients.cfn.get_waiter.assert_called_once_with("stack_update_complete")

    def test_wait_delete_uses_stack_delete_complete_waiter(self) -> None:
        """wait('delete') requests the stack_delete_complete waiter."""
        clients = _make_clients()
        stack = _make_stack(clients)
        stack.wait("delete")
        clients.cfn.get_waiter.assert_called_once_with("stack_delete_complete")

    def test_wait_raises_stack_wait_error_on_waiter_failure(self) -> None:
        """wait() wraps waiter exceptions in StackWaitError."""
        import pytest

        from ember_aws.stack import StackWaitError

        clients = _make_clients()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("Waiter failed: stack rolled back")
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        with pytest.raises(StackWaitError):
            stack.wait("create")

    def test_wait_passes_stack_name_to_waiter(self) -> None:
        """wait() passes the correct StackName to the waiter."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        stack.wait("create")
        mock_waiter.wait.assert_called_once_with(StackName="ember-default")


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


class TestStackDelete:
    """Stack.delete() calls cfn.delete_stack."""

    def test_delete_calls_cfn_delete_stack(self) -> None:
        """delete() calls cfn.delete_stack with the correct StackName."""
        clients = _make_clients()
        stack = _make_stack(clients)
        stack.delete()
        clients.cfn.delete_stack.assert_called_once_with(StackName="ember-default")


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------


class TestStackUpdate:
    """Stack.update() creates and executes a change set."""

    def test_update_returns_true_when_changes_applied(self) -> None:
        """update() returns True when the change set is executed successfully."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        result = stack.update(params={"InstanceType": "g6e.xlarge"})
        assert result is True

    def test_update_returns_false_when_no_changes(self) -> None:
        """update() returns False when the change set is empty."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("no changes to deploy")
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        result = stack.update(params={"InstanceType": "g6e.xlarge"})
        assert result is False

    def test_update_returns_false_on_empty_change_set(self) -> None:
        """update() returns False when exception message contains 'empty'."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("Change set is empty")
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        result = stack.update(params={})
        assert result is False

    def test_update_reraises_non_empty_exceptions(self) -> None:
        """update() re-raises exceptions that are not about empty change sets."""
        import pytest

        clients = _make_clients()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("InsufficientCapabilities")
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        with pytest.raises(Exception, match="InsufficientCapabilities"):
            stack.update(params={"InstanceType": "g6e.xlarge"})

    def test_update_excludes_internal_keys_from_cfn_parameters(self) -> None:
        """update() must not send internal _-prefixed keys as CFN parameters."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        stack.update(params={"InstanceType": "g6e.xlarge", "_template_body": "<t>"})
        call_kwargs = clients.cfn.create_change_set.call_args.kwargs
        keys = [p["ParameterKey"] for p in call_kwargs["Parameters"]]
        assert "_template_body" not in keys

    def test_update_calls_execute_change_set(self) -> None:
        """update() calls execute_change_set when changes are present."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        stack.update(params={"InstanceType": "g6e.xlarge"})
        clients.cfn.execute_change_set.assert_called_once()

    def test_update_passes_capability_named_iam(self) -> None:
        """update() acknowledges the template's named IAM resources."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        stack.update(params={"InstanceType": "g6e.xlarge"})
        call_kwargs = clients.cfn.create_change_set.call_args.kwargs
        assert "CAPABILITY_NAMED_IAM" in call_kwargs["Capabilities"]


# ---------------------------------------------------------------------------
# prepare_change_set()
# ---------------------------------------------------------------------------


class TestStackPrepareChangeSet:
    """Stack.prepare_change_set() creates a change set and returns its name."""

    def test_prepare_change_set_returns_name_on_success(self) -> None:
        """prepare_change_set() returns the change set name when successful."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        result = stack.prepare_change_set(params={"InstanceType": "g6e.xlarge"})
        assert result is not None
        assert result.startswith("ember-update-")

    def test_prepare_change_set_passes_capability_named_iam(self) -> None:
        """prepare_change_set() acknowledges the template's named IAM resources."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        stack.prepare_change_set(params={"InstanceType": "g6e.xlarge"})
        call_kwargs = clients.cfn.create_change_set.call_args.kwargs
        assert "CAPABILITY_NAMED_IAM" in call_kwargs["Capabilities"]

    def test_prepare_change_set_returns_none_when_empty(self) -> None:
        """prepare_change_set() returns None when the change set is empty."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("no changes to deploy")
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        result = stack.prepare_change_set(params={})
        assert result is None

    def test_prepare_change_set_reraises_non_empty_exceptions(self) -> None:
        """prepare_change_set() re-raises non-empty-change-set exceptions."""
        import pytest

        clients = _make_clients()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("AccessDenied")
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        with pytest.raises(Exception, match="AccessDenied"):
            stack.prepare_change_set(params={})


# ---------------------------------------------------------------------------
# change_set_has_replacement()
# ---------------------------------------------------------------------------


class TestStackChangeSetHasReplacement:
    """Stack.change_set_has_replacement() inspects change set resources."""

    def test_returns_true_when_replacement_is_true(self) -> None:
        """Returns True when a resource change has Replacement='True'."""
        clients = _make_clients()
        clients.cfn.describe_change_set.return_value = {
            "Changes": [
                {
                    "ResourceChange": {
                        "LogicalResourceId": "Instance",
                        "Replacement": "True",
                    }
                }
            ]
        }
        stack = _make_stack(clients)
        assert stack.change_set_has_replacement("cs-001") is True

    def test_returns_true_when_replacement_is_conditional(self) -> None:
        """Returns True when a resource change has Replacement='Conditional'."""
        clients = _make_clients()
        clients.cfn.describe_change_set.return_value = {
            "Changes": [
                {
                    "ResourceChange": {
                        "LogicalResourceId": "Instance",
                        "Replacement": "Conditional",
                    }
                }
            ]
        }
        stack = _make_stack(clients)
        assert stack.change_set_has_replacement("cs-001") is True

    def test_returns_false_when_no_replacement(self) -> None:
        """Returns False when no resource change requires replacement."""
        clients = _make_clients()
        clients.cfn.describe_change_set.return_value = {
            "Changes": [
                {
                    "ResourceChange": {
                        "LogicalResourceId": "SecurityGroup",
                        "Replacement": "False",
                    }
                }
            ]
        }
        stack = _make_stack(clients)
        assert stack.change_set_has_replacement("cs-001") is False

    def test_returns_false_when_no_changes(self) -> None:
        """Returns False when the change set has no changes."""
        clients = _make_clients()
        clients.cfn.describe_change_set.return_value = {"Changes": []}
        stack = _make_stack(clients)
        assert stack.change_set_has_replacement("cs-001") is False


# ---------------------------------------------------------------------------
# execute_change_set()
# ---------------------------------------------------------------------------


class TestStackExecuteChangeSet:
    """Stack.execute_change_set() calls cfn.execute_change_set."""

    def test_execute_change_set_calls_cfn(self) -> None:
        """execute_change_set() calls cfn.execute_change_set with correct args."""
        clients = _make_clients()
        stack = _make_stack(clients)
        stack.execute_change_set("cs-001")
        clients.cfn.execute_change_set.assert_called_once_with(
            StackName="ember-default",
            ChangeSetName="cs-001",
        )


# ---------------------------------------------------------------------------
# update_has_replacement()
# ---------------------------------------------------------------------------


class TestStackUpdateHasReplacement:
    """Stack.update_has_replacement() is a convenience wrapper."""

    def test_returns_false_when_change_set_is_empty(self) -> None:
        """Returns False when prepare_change_set returns None (empty)."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("no changes to deploy")
        clients.cfn.get_waiter.return_value = mock_waiter

        stack = _make_stack(clients)
        result = stack.update_has_replacement(params={})
        assert result is False

    def test_returns_true_when_change_set_has_replacement(self) -> None:
        """Returns True when the change set has a replacement resource."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        clients.cfn.get_waiter.return_value = mock_waiter
        clients.cfn.describe_change_set.return_value = {
            "Changes": [
                {
                    "ResourceChange": {
                        "LogicalResourceId": "Instance",
                        "Replacement": "True",
                    }
                }
            ]
        }
        stack = _make_stack(clients)
        result = stack.update_has_replacement(params={"InstanceType": "g6e.xlarge"})
        assert result is True

    def test_returns_false_when_no_replacement_in_change_set(self) -> None:
        """Returns False when the change set has no replacement resources."""
        clients = _make_clients()
        mock_waiter = MagicMock()
        clients.cfn.get_waiter.return_value = mock_waiter
        clients.cfn.describe_change_set.return_value = {
            "Changes": [
                {
                    "ResourceChange": {
                        "LogicalResourceId": "SecurityGroup",
                        "Replacement": "False",
                    }
                }
            ]
        }
        stack = _make_stack(clients)
        result = stack.update_has_replacement(params={"InstanceType": "g6e.xlarge"})
        assert result is False


# ---------------------------------------------------------------------------
# pick_subnets() error paths
# ---------------------------------------------------------------------------


class TestStackPickSubnetsErrors:
    """Stack.pick_subnets() raises ValueError when no VPC or subnet is found."""

    def test_raises_when_no_default_vpc(self) -> None:
        """pick_subnets() raises ValueError when no default VPC exists."""
        import pytest

        clients = _make_clients()
        clients.ec2.describe_vpcs.return_value = {"Vpcs": []}

        stack = _make_stack(clients)
        with pytest.raises(ValueError, match="no default VPC"):
            stack.pick_subnets("g6e.xlarge")

    def test_raises_when_no_matching_subnet(self) -> None:
        """pick_subnets() raises ValueError when no subnet is in an AZ offering the
        type."""
        import pytest

        clients = _make_clients()
        clients.ec2.describe_vpcs.return_value = {
            "Vpcs": [{"VpcId": "vpc-default", "IsDefault": True}]
        }
        clients.ec2.describe_instance_type_offerings.return_value = {
            "InstanceTypeOfferings": [
                {
                    "InstanceType": "g6e.xlarge",
                    "Location": "us-east-1a",
                    "LocationType": "availability-zone",
                }
            ]
        }
        # Subnet is in a different AZ
        clients.ec2.describe_subnets.return_value = {
            "Subnets": [
                {
                    "SubnetId": "subnet-bbb",
                    "VpcId": "vpc-default",
                    "AvailabilityZone": "us-east-1b",
                }
            ]
        }
        stack = _make_stack(clients)
        with pytest.raises(ValueError, match="no subnet"):
            stack.pick_subnets("g6e.xlarge")


# ---------------------------------------------------------------------------
# outputs() edge cases
# ---------------------------------------------------------------------------


class TestStackOutputsEdgeCases:
    """Stack.outputs() handles edge cases."""

    def test_outputs_returns_empty_dict_when_no_stacks(self) -> None:
        """outputs() returns {} when describe_stacks returns no stacks."""
        clients = _make_clients()
        clients.cfn.describe_stacks.return_value = {"Stacks": []}
        stack = _make_stack(clients)
        assert stack.outputs() == {}

    def test_outputs_returns_empty_dict_when_no_outputs_key(self) -> None:
        """outputs() returns {} when the stack has no Outputs key."""
        clients = _make_clients()
        clients.cfn.describe_stacks.return_value = {
            "Stacks": [{"StackName": "ember-default", "StackStatus": "CREATE_COMPLETE"}]
        }
        stack = _make_stack(clients)
        assert stack.outputs() == {}


# ---------------------------------------------------------------------------
# exists() edge cases
# ---------------------------------------------------------------------------


class TestStackExistsEdgeCases:
    """Stack.exists() re-raises unexpected ClientErrors."""

    def test_exists_reraises_non_validation_error(self) -> None:
        """exists() re-raises ClientErrors that are not ValidationError."""
        import pytest
        from botocore.exceptions import ClientError

        clients = _make_clients()
        clients.cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "DescribeStacks",
        )
        stack = _make_stack(clients)
        with pytest.raises(ClientError):
            stack.exists()
