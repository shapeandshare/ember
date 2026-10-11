"""LifecycleControl: stop, start, destroy, and rotate_token for an ember deployment."""

from __future__ import annotations

import os
import secrets
import sys
from typing import Any

from .health import wait_healthy
from .names import DeploymentName
from .stack import Stack


class LifecycleControl:
    """Stop, start, destroy, and rotate the auth token for an ember deployment.

    This class handles the control-plane operations that act on an already-deployed
    ember GPU instance.  It is intentionally separate from
    :class:`~ember_aws.lifecycle.Lifecycle` (which owns ``deploy`` and ``token``)
    to keep both modules under the 400-line limit (Article X §10.3).

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    tailscale : Any
        A :class:`~ember_aws.tailscale_client.TailscaleClient` instance (or mock).
    """

    def __init__(self, clients: Any, tailscale: Any) -> None:
        self._clients = clients
        self._tailscale = tailscale

    # ------------------------------------------------------------------
    # stop
    # ------------------------------------------------------------------

    def stop(self, deployment: Any) -> None:
        """Stop the EC2 instance and wait for the ``stopped`` state.

        If the instance is already stopped, prints ``already stopped`` and
        returns without making any EC2 call.

        Parameters
        ----------
        deployment : Any
            A :class:`~ember_aws.deployment.Deployment` instance.
        """
        names = DeploymentName(name=deployment.name)
        instance_id = self._get_instance_id(names)
        state = self._get_instance_state(instance_id)

        if state == "stopped":
            print("already stopped")
            return

        self._clients.ec2.stop_instances(InstanceIds=[instance_id])
        waiter = self._clients.ec2.get_waiter("instance_stopped")
        waiter.wait(InstanceIds=[instance_id])

    # ------------------------------------------------------------------
    # start
    # ------------------------------------------------------------------

    def start(self, deployment: Any) -> None:
        """Start the EC2 instance and wait for health.

        If the instance is already running, prints ``already running: <url>``
        and returns.  Otherwise, mints a fresh Tailscale join key only when
        the device is absent from the tailnet, starts the instance, and waits
        for the health endpoint to report ``engine.device == "cuda"``.

        Parameters
        ----------
        deployment : Any
            A :class:`~ember_aws.deployment.Deployment` instance.
        """
        names = DeploymentName(name=deployment.name)
        dns_info = self._tailscale.tailnet_dns()
        tailnet_suffix = dns_info.get("suffix", "")
        url = f"https://{names.hostname}.{tailnet_suffix}"

        instance_id = self._get_instance_id(names)
        state = self._get_instance_state(instance_id)

        if state == "running":
            print(f"already running: {url}")
            return

        # Mint a fresh join key only if the device is missing from the tailnet.
        if not self._device_on_tailnet(names.hostname, deployment.tailscale_tag):
            key_info = self._tailscale.mint_join_key(deployment.tailscale_tag)
            join_key_value: str = key_info.get("key", "")
            self._clients.ssm.put_parameter(
                Name=names.join_key_param,
                Value=join_key_value,
                Type="SecureString",
                Overwrite=True,
            )

        self._clients.ec2.start_instances(InstanceIds=[instance_id])

        token_val = self._read_token(names)
        timeout_s = int(os.environ.get("EMBER_AWS_HEALTH_TIMEOUT", "1200"))
        wait_healthy(url=url, token=token_val, timeout_s=timeout_s)

    # ------------------------------------------------------------------
    # destroy
    # ------------------------------------------------------------------

    def destroy(self, deployment: Any, confirm: str | None) -> None:
        """Destroy the deployment: tailnet devices → stack → SSM params.

        Refuses (exit 3) when ``confirm`` does not exactly match the
        deployment name.  Prints ``nothing deployed`` (exit 0) when there is
        no stack to delete.  Never touches the cache stack.

        Deletion order:
        1. Delete tailnet devices.
        2. Delete the CloudFormation stack.
        3. Wait for stack deletion.
        4. Delete every ``/ember/<name>/*`` SSM parameter.

        Parameters
        ----------
        deployment : Any
            A :class:`~ember_aws.deployment.Deployment` instance.
        confirm : str | None
            Must equal ``deployment.name`` to proceed; any other value exits 3.
        """
        names = DeploymentName(name=deployment.name)

        if confirm != deployment.name:
            print(
                f"error: pass --confirm {deployment.name} to destroy this deployment",
                file=sys.stderr,
            )
            sys.exit(3)

        stack = Stack(clients=self._clients, names=names)
        if not stack.exists():
            self._tailscale.delete_devices(names.hostname, deployment.tailscale_tag)
            self._delete_ssm_params(names)
            print("nothing deployed")
            return

        # 1. Delete tailnet devices.
        self._tailscale.delete_devices(names.hostname, deployment.tailscale_tag)

        # 2. Delete the stack.
        self._clients.cfn.delete_stack(StackName=names.stack_name)

        # 3. Wait for stack deletion. Failures propagate (the CLI exits 2) so
        #    step 4 is skipped and a still-live instance keeps its SSM config.
        stack.wait("delete")

        # 4. Delete every /ember/<name>/* SSM parameter.
        self._delete_ssm_params(names)

    # ------------------------------------------------------------------
    # rotate_token
    # ------------------------------------------------------------------

    def rotate_token(self, deployment: Any) -> None:
        """Rotate the server auth token: overwrite SSM param, reboot, wait for health.

        Generates a new random token, overwrites the SSM ``SecureString``
        parameter, reboots the instance, then waits for the health endpoint
        to confirm the instance is healthy again.  The new token is never
        printed to stdout or stderr.

        Parameters
        ----------
        deployment : Any
            A :class:`~ember_aws.deployment.Deployment` instance.
        """
        names = DeploymentName(name=deployment.name)
        dns_info = self._tailscale.tailnet_dns()
        tailnet_suffix = dns_info.get("suffix", "")
        url = f"https://{names.hostname}.{tailnet_suffix}"

        # 1. Overwrite the token parameter with a fresh value.
        new_token = secrets.token_urlsafe(32)
        self._clients.ssm.put_parameter(
            Name=names.token_param,
            Value=new_token,
            Type="SecureString",
            Overwrite=True,
        )

        # 2. Reboot the instance so it picks up the new token.
        instance_id = self._get_instance_id(names)
        self._clients.ec2.reboot_instances(InstanceIds=[instance_id])

        # 3. Wait for health with the new token.
        timeout_s = int(os.environ.get("EMBER_AWS_HEALTH_TIMEOUT", "1200"))
        wait_healthy(url=url, token=new_token, timeout_s=timeout_s)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_instance_id(self, names: DeploymentName) -> str:
        """Return the EC2 instance ID from the stack outputs.

        Parameters
        ----------
        names : DeploymentName
            Deployment name with derived stack path.

        Returns
        -------
        str
            The EC2 instance ID (e.g. ``"i-0001"``).
        """
        stack = Stack(clients=self._clients, names=names)
        outputs = stack.outputs()
        return outputs.get("InstanceId", "")

    def _get_instance_state(self, instance_id: str) -> str:
        """Return the current EC2 instance state name.

        Parameters
        ----------
        instance_id : str
            The EC2 instance ID.

        Returns
        -------
        str
            State name such as ``"running"``, ``"stopped"``, ``"stopping"``, etc.
        """
        resp = self._clients.ec2.describe_instances(InstanceIds=[instance_id])
        reservations = resp.get("Reservations", [])
        if not reservations:
            return "unknown"
        instances = reservations[0].get("Instances", [])
        if not instances:
            return "unknown"
        state: str = instances[0].get("State", {}).get("Name", "unknown")
        return state

    def _device_on_tailnet(self, hostname: str, tag: str) -> bool:
        """Return True if a device with the given hostname and tag is on the tailnet.

        Parameters
        ----------
        hostname : str
            The exact hostname to match (e.g. ``"ember-default"``).
        tag : str
            The tag that must be present (e.g. ``"tag:ember"``).

        Returns
        -------
        bool
            ``True`` when a matching device is found.
        """
        devices = self._tailscale.devices()
        for device in devices:
            device_hostname = device.get("hostname", "")
            device_tags: list[str] = device.get("tags", [])
            if device_hostname == hostname and tag in device_tags:
                return True
        return False

    def _read_token(self, names: DeploymentName) -> str:
        """Read the server auth token from SSM.

        Parameters
        ----------
        names : DeploymentName
            Deployment name with derived SSM paths.

        Returns
        -------
        str
            The decrypted token value.
        """
        resp = self._clients.ssm.get_parameter(
            Name=names.token_param, WithDecryption=True
        )
        token: str = resp["Parameter"]["Value"]
        return token

    def _delete_ssm_params(self, names: DeploymentName) -> None:
        """Delete all SSM parameters under ``/ember/<name>/``.

        Uses ``get_parameters_by_path`` to enumerate and ``delete_parameters``
        to remove them in batches of up to 10 (the SSM API limit).

        Parameters
        ----------
        names : DeploymentName
            Deployment name with derived SSM prefix.
        """
        prefix = names.ssm_prefix
        resp = self._clients.ssm.get_parameters_by_path(
            Path=prefix,
            Recursive=True,
            WithDecryption=False,
        )
        param_names = [p["Name"] for p in resp.get("Parameters", [])]
        if not param_names:
            return

        # SSM delete_parameters accepts up to 10 names per call.
        batch_size = 10
        for i in range(0, len(param_names), batch_size):
            batch = param_names[i : i + batch_size]
            self._clients.ssm.delete_parameters(Names=batch)
