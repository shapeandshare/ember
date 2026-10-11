"""Lifecycle: deploy and token operations for an ember AWS GPU deployment."""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

from .deployment import Deployment
from .health import HealthTimeout, wait_healthy
from .lifecycle_update import LifecycleUpdate
from .names import DeploymentName
from .sizing_status import SizingStatus
from .sizing_table import SizingError, SizingTable
from .stack import Stack, StackWaitError

#: Path to sizing.json relative to this file.
_SIZING_JSON = Path(__file__).parent.parent / "sizing.json"


class StackDeployError(Exception):
    """Raised when a CloudFormation stack operation fails.

    Parameters
    ----------
    message : str
        Human-readable description of the failure, including the first
        ``CREATE_FAILED`` event reason when available.
    """


class Lifecycle:
    """Deploy and manage an ember AWS GPU deployment.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    tailscale : Any
        A :class:`~ember_aws.tailscale_client.TailscaleClient` instance (or mock).
    model_cache : Any
        A :class:`~ember_aws.model_cache.ModelCache` instance (or mock).
    preflight : Any
        A :class:`~ember_aws.preflight.Preflight` instance (or mock).
    sizing_path : Path | None
        Path to ``sizing.json``; defaults to the bundled file.
    """

    def __init__(
        self,
        clients: Any,
        tailscale: Any,
        model_cache: Any,
        preflight: Any,
        sizing_path: Path | None = None,
    ) -> None:
        self._clients = clients
        self._tailscale = tailscale
        self._model_cache = model_cache
        self._preflight = preflight
        self._sizing_path = sizing_path or _SIZING_JSON

    # ------------------------------------------------------------------
    # deploy
    # ------------------------------------------------------------------

    def deploy(self, deployment: Deployment) -> None:
        """Deploy (or create) the ember GPU instance.

        Follows the T020 order exactly:
        1. preflight
        2. ModelCache.status; if not complete → ModelCache.add
        3. SSM put_parameter for config (incremented generation)
        4. Token only if absent (SecureString, 32 random bytes, urlsafe)
        5. delete tailnet devices
        6. mint and put the join key (SecureString)
        7. create_stack with resolved ImageId and subnet parameters and tags
        8. wait
        9. health poll

        Parameters
        ----------
        deployment : Deployment
            The desired deployment state.

        Raises
        ------
        SystemExit
            Exit code 1 for validation/sizing failures; 2 for stack failures.
        """
        names = DeploymentName(name=deployment.name)

        # 0. Resolve sizing (before preflight so we can exit 1 early).
        sizing = SizingTable.load(self._sizing_path)
        try:
            entry = sizing.resolve(deployment.model, deployment.instance_type)
        except SizingError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)

        if entry.status == SizingStatus.TIGHT:
            print(
                f"warning: instance type {entry.instance_type!r} is a tight fit for"
                f" model {deployment.model!r} (gpu_memory_gib={entry.gpu_memory_gib});"
                " consider g6e.xlarge for more headroom",
                file=sys.stderr,
            )

        # 1. Preflight.
        results = self._preflight.run(deployment)
        blocking_failures = [r for r in results if not r.ok and r.blocking]
        if blocking_failures:
            for r in results:
                if not r.ok:
                    marker = "✗" if r.blocking else "!"
                    print(f"{marker} {r.check.value}: {r.problem} — fix: {r.fix}")
            sys.exit(1)

        # 2. Cache check / add.
        import ember.models as ember_models  # import-placement:allow

        spec = ember_models.REGISTRY.get(deployment.model)
        revision = (spec.revision or "latest") if spec else "latest"
        cache_status = self._model_cache.status(deployment.model, revision)
        if cache_status != "complete":
            self._model_cache.add(deployment.model)

        # If the stack already exists, delegate to the update path.
        stack_check = Stack(clients=self._clients, names=names)
        if stack_check.exists():
            updater = LifecycleUpdate(
                clients=self._clients,
                tailscale=self._tailscale,
                sizing_path=self._sizing_path,
            )
            updater.update(deployment, self._model_cache)
            return

        # 3. SSM put_parameter for config (with incremented generation).
        from .instance_config import InstanceConfig  # import-placement:allow

        current_gen = self._read_current_generation(names)
        new_gen = current_gen + 1
        s3_uri = (
            f"s3://{self._resolve_bucket(names)}/models/{deployment.model}/{revision}"
        )
        config = InstanceConfig(
            ember_version=deployment.ember_version,
            model_s3_uri=s3_uri,
            max_request_length=entry.request_cap,
            idle_minutes=deployment.idle_minutes,
            generation=new_gen,
        )
        self._clients.ssm.put_parameter(
            Name=names.config_param,
            Value=config.model_dump_json(),
            Type="String",
            Overwrite=True,
        )

        # 4. Token only if absent.
        if not self._token_exists(names):
            token_value = secrets.token_urlsafe(32)
            self._clients.ssm.put_parameter(
                Name=names.token_param,
                Value=token_value,
                Type="SecureString",
                Overwrite=False,
            )

        # 5. Delete tailnet devices.
        self._tailscale.delete_devices(names.hostname, deployment.tailscale_tag)

        # 6. Mint and put the join key.
        key_info = self._tailscale.mint_join_key(deployment.tailscale_tag)
        join_key_value: str = key_info.get("key", "")
        self._clients.ssm.put_parameter(
            Name=names.join_key_param,
            Value=join_key_value,
            Type="SecureString",
            Overwrite=True,
        )

        # 7. Create stack.
        stack = Stack(clients=self._clients, names=names)
        ami_id = stack.resolve_image_id(deployment.region)
        subnet_id, vpc_id = stack.pick_subnet(entry.instance_type)

        from .user_data import UserData  # import-placement:allow

        rendered_ud = UserData.render(
            names=names,
            region=deployment.region,
            config=config,
            tailscale_tag=deployment.tailscale_tag,
        )
        template_body = UserData.template_body(rendered_ud)

        params: dict[str, str] = {
            "DeploymentName": deployment.name,
            "InstanceType": entry.instance_type,
            "Capacity": deployment.capacity.value,
            "ImageId": ami_id,
            "SubnetId": subnet_id,
            "VpcId": vpc_id,
            "CacheBucket": self._resolve_bucket(names),
            "ModelPrefix": f"models/{deployment.model}/{revision}/",
            "TailscaleTag": deployment.tailscale_tag,
            # Internal: pass the rendered template body through the params dict
            # so Stack.create can use it without a separate argument.
            "_template_body": template_body,
        }
        tags = [
            {"Key": "ember:deployment", "Value": deployment.name},
            {"Key": "ember:managed-by", "Value": "ember_aws"},
        ]
        stack.create(params=params, tags=tags)

        # 8. Wait.
        try:
            stack.wait("create")
        except (StackWaitError, StackDeployError) as exc:
            reason = stack.first_failure_reason() or str(exc)
            print(f"error: stack creation failed: {reason}", file=sys.stderr)
            sys.exit(2)
        except Exception as exc:
            reason = stack.first_failure_reason() or str(exc)
            print(f"error: stack creation failed: {reason}", file=sys.stderr)
            sys.exit(2)

        # 9. Health poll.
        dns_info = self._tailscale.tailnet_dns()
        tailnet_suffix = dns_info.get("suffix", "")
        url = f"https://{names.hostname}.{tailnet_suffix}"

        token_val = self._read_token(names)
        timeout_s = int(os.environ.get("EMBER_AWS_HEALTH_TIMEOUT", "1200"))

        try:
            health = wait_healthy(url=url, token=token_val, timeout_s=timeout_s)
        except HealthTimeout as exc:
            print(f"error: health poll timed out: {exc}", file=sys.stderr)
            sys.exit(2)

        # Print success output matching contracts/cli.md.
        device = (health.get("engine") or {}).get("device", "cuda")
        version = health.get("version", deployment.ember_version)
        print(
            f'ember deployment "{deployment.name}" is healthy on'
            f" {entry.instance_type} ({device}, ember {version})"
        )
        print(f"  url:   {url}")
        next_cmd = (
            f"  next:  export EMBER_AUTH_TOKEN="
            f'"$(make -s aws-token NAME={deployment.name})"'
            f"   # or: ember_aws status --show-token"
        )
        print(next_cmd)
        print(f"         ember init --opencode --server-url {url}")

    def replace(self, deployment: Deployment) -> None:
        """Replace the instance with the latest DLAMI.

        Delegates to :class:`~ember_aws.lifecycle_update.LifecycleUpdate.replace`.

        Parameters
        ----------
        deployment : Deployment
            The desired deployment state.
        """
        updater = LifecycleUpdate(
            clients=self._clients,
            tailscale=self._tailscale,
            sizing_path=self._sizing_path,
        )
        updater.replace(deployment, self._model_cache)

    def token(self, deployment: Deployment) -> None:
        """Print only the server auth token to stdout.

        The token is never logged or written to stderr.

        Parameters
        ----------
        deployment : Deployment
            The deployment whose token to retrieve.
        """
        names = DeploymentName(name=deployment.name)
        token_val = self._read_token(names)
        print(token_val)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _token_exists(self, names: DeploymentName) -> bool:
        """Return True if the server-token SSM parameter exists.

        Parameters
        ----------
        names : DeploymentName
            Deployment name with derived SSM paths.

        Returns
        -------
        bool
            ``True`` when the parameter is present.
        """
        from botocore.exceptions import ClientError  # import-placement:allow

        try:
            self._clients.ssm.get_parameter(
                Name=names.token_param, WithDecryption=False
            )
            return True
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if "ParameterNotFound" in code:
                return False
            raise

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
        from botocore.exceptions import ClientError  # import-placement:allow

        try:
            resp = self._clients.ssm.get_parameter(Name=names.config_param)
            config_json: str = resp["Parameter"]["Value"]
            config_data = json.loads(config_json)
            gen: int = config_data.get("generation", 0)
            return gen
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if "ParameterNotFound" in code:
                return 0
            raise
        except Exception:
            return 0

    def _resolve_bucket(self, names: DeploymentName) -> str:
        """Resolve the S3 cache bucket name.

        Parameters
        ----------
        names : DeploymentName
            Deployment name (unused here; kept for future per-deployment buckets).

        Returns
        -------
        str
            The S3 bucket name from the cache stack, or a placeholder.
        """
        if hasattr(self._model_cache, "_stack_bucket"):
            raw: object = self._model_cache._stack_bucket()
            bucket_name = str(raw) if raw else ""
            if bucket_name:
                return bucket_name
        # Fallback: try ensure_bucket if available
        if hasattr(self._model_cache, "ensure_bucket"):
            raw2: object = self._model_cache.ensure_bucket()
            if raw2:
                return str(raw2)
        return "ember-model-cache-bucket"
