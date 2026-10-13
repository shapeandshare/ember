"""LifecycleUpdate: in-place update and replace for an ember AWS GPU deployment."""

from __future__ import annotations

import os
from typing import Any

from . import stack_parameters
from .health import probe_health, wait_healthy
from .instance_config import InstanceConfig
from .lifecycle_state import LifecycleState
from .names import DeploymentName
from .sizing_table import SizingTable
from .stack import Stack


class LifecycleUpdate(LifecycleState):
    """In-place update and replace operations for an ember AWS GPU deployment.

    State reads (SSM config/token, generation, cache bucket) are inherited
    from :class:`~ember_aws.lifecycle_state.LifecycleState`.
    """

    def update(self, deployment: Any, model_cache: Any) -> None:
        """Update an existing deployment in place.

        Compares the desired :class:`~ember_aws.instance_config.InstanceConfig`
        to the stored one and takes the minimal action:

        - No change → prints ``up to date: <url>`` and returns.
        - Config-only change (version, model URI, idle minutes) → increments
          generation, puts the new config, reboots, waits for health.
        - Stack parameter change (instance type) with no replacement → creates
          a change set via ``stack.update()``; waits for health.
        - Stack parameter change with ``Replacement=True`` → deletes tailnet
          devices and mints a new join key *before* executing the change set;
          then waits for health.

        Parameters
        ----------
        deployment : Any
            A :class:`~ember_aws.deployment.Deployment` instance.
        model_cache : Any
            A :class:`~ember_aws.model_cache.ModelCache` instance.
        """
        names = DeploymentName(name=deployment.name)

        sizing = SizingTable.load(self._sizing_path)
        entry = sizing.resolve(deployment.model, deployment.instance_type)

        import ember.models as ember_models  # import-placement:allow

        spec = ember_models.REGISTRY.get(deployment.model)
        revision = (spec.revision or "latest") if spec else "latest"
        s3_uri = (
            f"s3://{self._resolve_bucket(names, model_cache)}"
            f"/models/{deployment.model}/{revision}"
        )

        current_gen = self._read_current_generation(names)
        desired_config = InstanceConfig(
            ember_version=deployment.ember_version,
            model_s3_uri=s3_uri,
            max_request_length=entry.request_cap,
            idle_minutes=deployment.idle_minutes,
            generation=current_gen,
        )

        stored_config = self._read_stored_config(names)

        dns_info = self._tailscale.tailnet_dns()
        tailnet_suffix = dns_info.get("suffix", "")
        url = f"https://{names.hostname}.{tailnet_suffix}"

        stack = Stack(clients=self._clients, names=names)
        from .user_data import UserData  # import-placement:allow

        template_body = UserData.template_body(
            UserData.render(
                names=names,
                region=deployment.region,
                config=desired_config,
                tailscale_tag=deployment.tailscale_tag,
            )
        )
        stack_params: dict[str, str] = {
            **stack_parameters.read(self._clients, names.stack_name),
            "InstanceType": entry.instance_type,
            "ModelPrefix": f"models/{deployment.model}/{revision}/",
            "_template_body": template_body,
        }

        config_changed = stored_config is None or not self._configs_equal(
            desired_config, stored_config
        )

        has_replacement = stack.update_has_replacement(stack_params)

        token_val = self._read_token(names)
        health_now = probe_health(url, token_val)
        prior_pid = health_now.get("pid") if health_now else None

        if has_replacement:
            if config_changed:
                new_gen = current_gen + 1
                new_config = InstanceConfig(
                    ember_version=deployment.ember_version,
                    model_s3_uri=s3_uri,
                    max_request_length=entry.request_cap,
                    idle_minutes=deployment.idle_minutes,
                    generation=new_gen,
                )
                self._clients.ssm.put_parameter(
                    Name=names.config_param,
                    Value=new_config.model_dump_json(),
                    Type="String",
                    Overwrite=True,
                )
            self._tailscale.delete_devices(names.hostname, deployment.tailscale_tag)
            key_info = self._tailscale.mint_join_key(deployment.tailscale_tag)
            join_key_value: str = key_info.get("key", "")
            self._clients.ssm.put_parameter(
                Name=names.join_key_param,
                Value=join_key_value,
                Type="SecureString",
                Overwrite=True,
            )
            change_set_name = stack.prepare_change_set(stack_params)
            if change_set_name is not None:
                stack.execute_change_set(change_set_name)
                stack.wait("update")
        else:
            if config_changed:
                new_gen = current_gen + 1
                new_config = InstanceConfig(
                    ember_version=deployment.ember_version,
                    model_s3_uri=s3_uri,
                    max_request_length=entry.request_cap,
                    idle_minutes=deployment.idle_minutes,
                    generation=new_gen,
                )
                self._clients.ssm.put_parameter(
                    Name=names.config_param,
                    Value=new_config.model_dump_json(),
                    Type="String",
                    Overwrite=True,
                )

            changed = stack.update(stack_params)
            if changed:
                stack.wait("update")
            elif config_changed:
                self._restart_instance(names, deployment)
            else:
                print(f"up to date: {url}")
                return

        timeout_s = int(os.environ.get("EMBER_AWS_HEALTH_TIMEOUT", "1200"))
        health = wait_healthy(
            url=url, token=token_val, timeout_s=timeout_s, previous_pid=prior_pid
        )

        device = (health.get("engine") or {}).get("device", "cuda")
        version = health.get("version", deployment.ember_version)
        print(
            f'ember deployment "{deployment.name}" is healthy on'
            f" {entry.instance_type} ({device}, ember {version})"
        )
        print(f"  url:   {url}")

    def replace(self, deployment: Any, model_cache: Any) -> None:
        """Replace the instance with the latest DLAMI.

        Re-resolves the DLAMI ID, forces replacement via a change set with a
        new ``ImageId``, deletes tailnet devices and mints a new join key
        *before* executing the change set, then waits for health.  The
        deployed state (model, instance type, version, idle stop) is read
        from SSM and the stack and preserved; only the AMI changes.

        Parameters
        ----------
        deployment : Any
            A :class:`~ember_aws.deployment.Deployment` instance.
        model_cache : Any
            A :class:`~ember_aws.model_cache.ModelCache` instance.
        """
        names = DeploymentName(name=deployment.name)

        stored = self._read_stored_config(names)
        params = stack_parameters.read(self._clients, names.stack_name)
        if stored is not None:
            deployment = self._with_deployed_state(deployment, stored, params)

        sizing = SizingTable.load(self._sizing_path)
        entry = sizing.resolve(deployment.model, deployment.instance_type)

        import ember.models as ember_models  # import-placement:allow

        spec = ember_models.REGISTRY.get(deployment.model)
        revision = (spec.revision or "latest") if spec else "latest"
        s3_uri = (
            f"s3://{self._resolve_bucket(names, model_cache)}"
            f"/models/{deployment.model}/{revision}"
        )

        stack = Stack(clients=self._clients, names=names)
        ami_id = stack.resolve_image_id(deployment.region)
        from .user_data import UserData  # import-placement:allow

        render_config = InstanceConfig(
            ember_version=deployment.ember_version,
            model_s3_uri=s3_uri,
            max_request_length=entry.request_cap,
            idle_minutes=deployment.idle_minutes,
            generation=self._read_current_generation(names),
        )
        stack_params: dict[str, str] = {
            **stack_parameters.read(self._clients, names.stack_name),
            "InstanceType": entry.instance_type,
            "ImageId": ami_id,
            "_template_body": UserData.template_body(
                UserData.render(
                    names=names,
                    region=deployment.region,
                    config=render_config,
                    tailscale_tag=deployment.tailscale_tag,
                )
            ),
        }

        # Prepare first: a no-op change set must not disturb the working
        # tailnet device or bump the generation for nothing.
        change_set_name = stack.prepare_change_set(stack_params)
        if change_set_name is None:
            print(f"already on the latest image ({ami_id}); nothing to replace")
            return

        current_gen = self._read_current_generation(names)
        new_gen = current_gen + 1
        new_config = InstanceConfig(
            ember_version=deployment.ember_version,
            model_s3_uri=s3_uri,
            max_request_length=entry.request_cap,
            idle_minutes=deployment.idle_minutes,
            generation=new_gen,
        )

        self._clients.ssm.put_parameter(
            Name=names.config_param,
            Value=new_config.model_dump_json(),
            Type="String",
            Overwrite=True,
        )

        self._tailscale.delete_devices(names.hostname, deployment.tailscale_tag)
        key_info = self._tailscale.mint_join_key(deployment.tailscale_tag)
        join_key_value: str = key_info.get("key", "")
        self._clients.ssm.put_parameter(
            Name=names.join_key_param,
            Value=join_key_value,
            Type="SecureString",
            Overwrite=True,
        )

        stack.execute_change_set(change_set_name)
        stack.wait("update")

        dns_info = self._tailscale.tailnet_dns()
        tailnet_suffix = dns_info.get("suffix", "")
        url = f"https://{names.hostname}.{tailnet_suffix}"

        token_val = self._read_token(names)
        timeout_s = int(os.environ.get("EMBER_AWS_HEALTH_TIMEOUT", "1200"))
        health = wait_healthy(url=url, token=token_val, timeout_s=timeout_s)

        device = (health.get("engine") or {}).get("device", "cuda")
        version = health.get("version", deployment.ember_version)
        print(
            f'ember deployment "{deployment.name}" is healthy on'
            f" {entry.instance_type} ({device}, ember {version})"
        )
        print(f"  url:   {url}")

    def _with_deployed_state(
        self,
        deployment: Any,
        stored: InstanceConfig,
        params: dict[str, str],
    ) -> Any:
        """Return the deployment carrying the deployed state's fields.

        ``replace`` changes only the AMI: the model, instance type, version,
        and idle stop must come from the stored SSM config and the stack's
        parameters, never from CLI defaults.

        Parameters
        ----------
        deployment : Any
            The requested deployment (its name is authoritative).
        stored : InstanceConfig
            The SSM config the running instance belongs to.
        params : dict[str, str]
            The stack's current parameter values.

        Returns
        -------
        Any
            A copy of ``deployment`` with the deployed state preserved.
        """
        parts = stored.model_s3_uri.rstrip("/").split("/")
        updates: dict[str, Any] = {
            "ember_version": stored.ember_version,
            "idle_minutes": stored.idle_minutes,
        }
        if len(parts) >= 2:
            updates["model"] = parts[-2]
        if params.get("InstanceType"):
            updates["instance_type"] = params["InstanceType"]
        return deployment.model_copy(update=updates)

    def _restart_instance(self, names: DeploymentName, deployment: Any) -> None:
        """Apply a config change: reboot a running instance or start a stopped one.

        EC2 rejects ``reboot_instances`` for a stopped instance, so start it
        instead, minting a fresh join key first when its tailnet device is
        gone.

        Parameters
        ----------
        names : DeploymentName
            Deployment name with derived stack and SSM paths.
        deployment : Any
            The desired deployment.
        """
        instance_id = self._get_instance_id(names)
        state = self._instance_state(instance_id)
        if state == "running":
            self._clients.ec2.reboot_instances(InstanceIds=[instance_id])
            return
        if not self._device_on_tailnet(names.hostname, deployment.tailscale_tag):
            key_info = self._tailscale.mint_join_key(deployment.tailscale_tag)
            self._clients.ssm.put_parameter(
                Name=names.join_key_param,
                Value=key_info.get("key", ""),
                Type="SecureString",
                Overwrite=True,
            )
        self._clients.ec2.start_instances(InstanceIds=[instance_id])

    def _instance_state(self, instance_id: str) -> str:
        """Return the EC2 instance state name (``"unknown"`` when absent).

        Parameters
        ----------
        instance_id : str
            The EC2 instance ID.

        Returns
        -------
        str
            State name such as ``"running"`` or ``"stopped"``.
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
        """Return True when the hostname+tag device is on the tailnet.

        Parameters
        ----------
        hostname : str
            Exact device hostname (e.g. ``"ember-default"``).
        tag : str
            Required tag (e.g. ``"tag:ember"``).

        Returns
        -------
        bool
            ``True`` when a matching device exists.
        """
        for device in self._tailscale.devices():
            if device.get("hostname") == hostname and tag in device.get("tags", []):
                return True
        return False

    def _get_instance_id(self, names: DeploymentName) -> str:
        """Return the EC2 instance ID from the stack outputs.

        Parameters
        ----------
        names : DeploymentName
            Deployment name with derived stack path.

        Returns
        -------
        str
            The EC2 instance ID.
        """
        stack = Stack(clients=self._clients, names=names)
        outputs = stack.outputs()
        return outputs.get("InstanceId", "")
