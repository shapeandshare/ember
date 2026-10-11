"""LifecycleState: shared SSM/EC2 state helpers for lifecycle operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .instance_config import InstanceConfig
from .names import DeploymentName

#: Path to sizing.json relative to this file.
_SIZING_JSON = Path(__file__).parent.parent / "sizing.json"


class LifecycleState:
    """Shared state reads for the lifecycle update and replace operations.

    Extracted from :class:`~ember_aws.lifecycle_update.LifecycleUpdate` to
    keep both modules under the 400-line limit (Article X §10.3).

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
