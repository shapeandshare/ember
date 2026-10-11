"""LifecycleUpdate: in-place update and replace for an ember AWS GPU deployment."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .health import wait_healthy
from .instance_config import InstanceConfig
from .names import DeploymentName
from .sizing_table import SizingTable
from .stack import Stack

#: Path to sizing.json relative to this file.
_SIZING_JSON = Path(__file__).parent.parent / "sizing.json"


class LifecycleUpdate:
    """In-place update and replace operations for an ember AWS GPU deployment.

    Separated from :class:`~ember_aws.lifecycle.Lifecycle` to keep both
    modules under the 400-line limit (Article X §10.3).

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    tailscale : Any
        A :class:`~ember_aws.tailscale_client.TailscaleClient` instance (or mock).
    sizing_path : Path | None
        Path to ``sizing.json``; defaults to the bundled file.
    """

    def __init__(
        self,
        clients: Any,
        tailscale: Any,
        sizing_path: Path | None = None,
    ) -> None:
        self._clients = clients
        self._tailscale = tailscale
        self._sizing_path = sizing_path or _SIZING_JSON

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
        stack_params: dict[str, str] = {
            "InstanceType": entry.instance_type,
            "ModelPrefix": f"models/{deployment.model}/{revision}/",
        }

        config_changed = stored_config is None or not self._configs_equal(
            desired_config, stored_config
        )

        has_replacement = stack.update_has_replacement(stack_params)

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
                instance_id = self._get_instance_id(names)
                self._clients.ec2.reboot_instances(InstanceIds=[instance_id])
            else:
                print(f"up to date: {url}")
                return

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

    def replace(self, deployment: Any, model_cache: Any) -> None:
        """Replace the instance with the latest DLAMI.

        Re-resolves the DLAMI ID, forces replacement via a change set with a
        new ``ImageId``, deletes tailnet devices and mints a new join key
        *before* executing the change set, then waits for health.

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

        stack = Stack(clients=self._clients, names=names)
        ami_id = stack.resolve_image_id(deployment.region)

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

        stack_params: dict[str, str] = {
            "InstanceType": entry.instance_type,
            "ImageId": ami_id,
        }

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

    def _configs_equal(self, a: InstanceConfig, b: InstanceConfig) -> bool:
        """Return True when two configs are identical ignoring generation.

        Parameters
        ----------
        a : InstanceConfig
            First config.
        b : InstanceConfig
            Second config.

        Returns
        -------
        bool
            ``True`` when all fields except ``generation`` are equal.
        """
        return (
            a.ember_version == b.ember_version
            and a.model_s3_uri == b.model_s3_uri
            and a.max_request_length == b.max_request_length
            and a.idle_minutes == b.idle_minutes
        )

    def _read_stored_config(self, names: DeploymentName) -> InstanceConfig | None:
        """Read the stored InstanceConfig from SSM, or None if absent.

        Parameters
        ----------
        names : DeploymentName
            Deployment name with derived SSM paths.

        Returns
        -------
        InstanceConfig | None
            The stored config, or ``None`` if the parameter does not exist.
        """
        from botocore.exceptions import ClientError  # import-placement:allow

        try:
            resp = self._clients.ssm.get_parameter(Name=names.config_param)
            config_json: str = resp["Parameter"]["Value"]
            data = json.loads(config_json)
            return InstanceConfig(**data)
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if "ParameterNotFound" in code:
                return None
            raise
        except Exception:
            return None

    def _read_current_generation(self, names: DeploymentName) -> int:
        """Read the current config generation from SSM, or 0 if absent.

        Parameters
        ----------
        names : DeploymentName
            Deployment name with derived SSM paths.

        Returns
        -------
        int
            The current generation number, or 0 if the parameter does not exist.
        """
        stored = self._read_stored_config(names)
        if stored is None:
            return 0
        return stored.generation

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

    def _resolve_bucket(self, names: DeploymentName, model_cache: Any) -> str:
        """Resolve the S3 cache bucket name.

        Parameters
        ----------
        names : DeploymentName
            Deployment name.
        model_cache : Any
            A :class:`~ember_aws.model_cache.ModelCache` instance.

        Returns
        -------
        str
            The S3 bucket name.
        """
        if hasattr(model_cache, "_stack_bucket"):
            raw: object = model_cache._stack_bucket()
            bucket_name = str(raw) if raw else ""
            if bucket_name:
                return bucket_name
        if hasattr(model_cache, "ensure_bucket"):
            raw2: object = model_cache.ensure_bucket()
            if raw2:
                return str(raw2)
        return "ember-model-cache-bucket"
