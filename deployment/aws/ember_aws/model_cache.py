"""ModelCache: S3-backed model cache for AWS GPU deployments."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .cache_guard import (
    _CACHE_STACK_NAME,
    _LIVE_STACK_STATUSES,
    CacheInUseError,
    ConfirmationError,
    check_no_deployments,
    check_not_in_use,
)
from .cache_uploader import CacheUploader

__all__ = ["CacheInUseError", "ConfirmationError", "ModelCache"]


class ModelCache:
    """S3-backed model cache for AWS GPU deployments.

    Manages the ``ember-model-cache`` CloudFormation stack and the S3 bucket
    it creates.  Files are uploaded with multipart transfer and skipped when
    their size and SHA-256 already match.  The manifest is written last so a
    partial upload is always detectable.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    downloader : Callable | None
        A callable with the same signature as
        ``huggingface_hub.snapshot_download``; defaults to the real function.
    """

    def __init__(
        self,
        clients: Any,
        downloader: Callable[..., str] | None = None,
    ) -> None:
        self._clients = clients
        if downloader is None:
            import huggingface_hub  # import-placement:allow

            self._downloader: Callable[..., str] = huggingface_hub.snapshot_download
        else:
            self._downloader = downloader

    def _stack_bucket(self) -> str | None:
        """Return the bucket name from the cache stack, or None if absent."""
        from botocore.exceptions import ClientError  # import-placement:allow

        try:
            resp = self._clients.cfn.describe_stacks(StackName=_CACHE_STACK_NAME)
            stacks = resp.get("Stacks", [])
            if not stacks:
                return None
            outputs = stacks[0].get("Outputs", [])
            for out in outputs:
                if out.get("OutputKey") == "BucketName":
                    return str(out["OutputValue"])
            return None
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if "ValidationError" in code or "does not exist" in str(exc):
                return None
            raise

    def ensure_bucket(self) -> str:
        """Ensure the cache stack and bucket exist, creating them if needed.

        Returns
        -------
        str
            The S3 bucket name.
        """
        existing = self._stack_bucket()
        if existing:
            return existing

        template_path = Path(__file__).resolve().parents[1] / "cache-template.yaml"
        template_body = template_path.read_text()

        self._clients.cfn.create_stack(
            StackName=_CACHE_STACK_NAME,
            TemplateBody=template_body,
            Capabilities=["CAPABILITY_IAM"],
        )
        waiter = self._clients.cfn.get_waiter("stack_create_complete")
        waiter.wait(StackName=_CACHE_STACK_NAME)

        bucket = self._stack_bucket()
        if not bucket:
            raise RuntimeError(
                f"stack {_CACHE_STACK_NAME!r} created but BucketName output not found"
            )
        return bucket

    def status(
        self,
        model: str,
        revision: str,
        bucket: str | None = None,
        prefix: str = "models/",
    ) -> str:
        """Return the cache status for a model revision.

        Parameters
        ----------
        model : str
            Registry key (e.g. ``"flash"``).
        revision : str
            Hugging Face commit hash or tag.
        bucket : str | None
            S3 bucket name; if ``None``, uses the managed cache stack.
        prefix : str
            S3 key prefix; defaults to ``"models/"``.

        Returns
        -------
        str
            One of ``"complete"``, ``"partial"``, or ``"absent"``.
        """
        from botocore.exceptions import ClientError  # import-placement:allow

        if bucket is None:
            bucket = self._stack_bucket()
            if not bucket:
                return "absent"

        manifest_key = f"{prefix}{model}/{revision}/manifest.json"
        try:
            self._clients.s3.head_object(Bucket=bucket, Key=manifest_key)
        except ClientError:
            return "absent"

        try:
            manifest_resp = self._clients.s3.get_object(Bucket=bucket, Key=manifest_key)
            manifest_body = manifest_resp["Body"].read()
            manifest = json.loads(manifest_body)
        except Exception:
            return "partial"

        files: list[dict[str, Any]] = manifest.get("files", [])
        for file_entry in files:
            file_key = f"{prefix}{model}/{revision}/{file_entry['path']}"
            expected_size = file_entry.get("size", -1)
            try:
                head = self._clients.s3.head_object(Bucket=bucket, Key=file_key)
                actual_size = head.get("ContentLength", -1)
                if actual_size != expected_size:
                    return "partial"
            except ClientError:
                return "partial"

        return "complete"

    def add(
        self,
        model: str,
        bucket: str | None = None,
        prefix: str = "models/",
    ) -> None:
        """Download and upload a model to the S3 cache.

        Parameters
        ----------
        model : str
            Registry key (e.g. ``"flash"``).
        bucket : str | None
            S3 bucket name.  If ``None``, the managed cache stack is used
            (created if absent).  Passing an explicit bucket skips stack
            creation entirely.
        prefix : str
            S3 key prefix; defaults to ``"models/"``.
        """
        import ember.models as ember_models  # import-placement:allow

        spec = ember_models.REGISTRY.get(model)
        if spec is None:
            raise ValueError(f"unknown model {model!r}")
        revision = spec.revision or "latest"

        if bucket is None:
            bucket = self.ensure_bucket()

        current_status = self.status(model, revision, bucket=bucket, prefix=prefix)
        if current_status == "complete":
            print(f"cached: {model}@{revision} (already complete)")
            return

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_dir = self._downloader(
                repo_id=spec.repo,
                revision=revision,
                local_dir=tmp_dir,
            )
            local_path = Path(local_dir)
            uploader = CacheUploader(self._clients.s3)
            uploader.upload(model, revision, bucket, prefix, local_path)

    def list(
        self,
        bucket: str | None = None,
        prefix: str = "models/",
    ) -> list[dict[str, Any]]:
        """List cached models with status, size, and using deployments.

        Every ``<model>/<revision>/`` prefix that holds objects is listed —
        including interrupted uploads, which have objects but no manifest and
        report ``"partial"``.

        Parameters
        ----------
        bucket : str | None
            S3 bucket name; if ``None``, uses the managed cache stack.
        prefix : str
            S3 key prefix; defaults to ``"models/"``.

        Returns
        -------
        list[dict[str, Any]]
            One entry per cached model revision with ``model``,
            ``revision``, ``status``, ``total_bytes`` (from the manifest, or
            ``None``), and ``deployments`` (names of deployments using it).
        """
        if bucket is None:
            bucket = self._stack_bucket()
            if not bucket:
                return []

        resp = self._clients.s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        pairs: set[tuple[str, str]] = set()
        for obj in resp.get("Contents", []):
            parts = obj["Key"][len(prefix) :].split("/")
            if len(parts) >= 3 and parts[0] and parts[1]:
                pairs.add((parts[0], parts[1]))

        deployments_by_uri = self._deployments_by_uri()
        results: list[dict[str, Any]] = []
        for model_name, rev in sorted(pairs):
            manifest_key = f"{prefix}{model_name}/{rev}/manifest.json"
            cache_status = self.status(model_name, rev, bucket=bucket, prefix=prefix)
            if cache_status == "absent":
                cache_status = "partial"
            uri = f"s3://{bucket}/{prefix}{model_name}/{rev}".rstrip("/")
            results.append(
                {
                    "model": model_name,
                    "revision": rev,
                    "status": cache_status,
                    "total_bytes": self._manifest_total_bytes(bucket, manifest_key),
                    "deployments": deployments_by_uri.get(uri, []),
                }
            )
        return results

    def _manifest_total_bytes(self, bucket: str, manifest_key: str) -> int | None:
        """Return the manifest's ``total_bytes``, or ``None`` when unreadable.

        Parameters
        ----------
        bucket : str
            S3 bucket name.
        manifest_key : str
            Key of the manifest object.

        Returns
        -------
        int | None
            The recorded total size in bytes, or ``None``.
        """
        try:
            body = self._clients.s3.get_object(Bucket=bucket, Key=manifest_key)
            manifest = json.loads(body["Body"].read())
            total = manifest.get("total_bytes")
            return int(total) if total is not None else None
        except Exception:
            return None

    def _deployments_by_uri(self) -> dict[str, list[str]]:
        """Map each active deployment's model URI to its deployment names.

        Returns
        -------
        dict[str, list[str]]
            Normalized ``model_s3_uri`` → deployment names; unreadable
            configs are skipped (this backs a listing, not a guard).
        """
        by_uri: dict[str, list[str]] = {}
        stacks = self._clients.cfn.list_stacks(StackStatusFilter=_LIVE_STACK_STATUSES)
        for stack_summary in stacks.get("StackSummaries", []):
            stack_name = stack_summary.get("StackName", "")
            if not stack_name.startswith("ember-") or stack_name == _CACHE_STACK_NAME:
                continue
            name = stack_name[len("ember-") :]
            try:
                resp = self._clients.ssm.get_parameter(Name=f"/ember/{name}/config")
                config = json.loads(resp["Parameter"]["Value"])
            except Exception:  # noqa: S112 - listing skips unreadable configs
                continue
            uri = str(config.get("model_s3_uri", "")).rstrip("/")
            if uri:
                by_uri.setdefault(uri, []).append(name)
        return by_uri

    def remove(
        self,
        model: str,
        revision: str,
        bucket: str | None = None,
        prefix: str = "models/",
    ) -> None:
        """Remove a cached model from S3.

        Parameters
        ----------
        model : str
            Registry key.
        revision : str
            Model revision.
        bucket : str | None
            S3 bucket name; if ``None``, uses the managed cache stack.
        prefix : str
            S3 key prefix; defaults to ``"models/"``.

        Raises
        ------
        CacheInUseError
            If any ``ember-*`` deployment stack's config points at this exact
            model revision.
        """
        if bucket is None:
            bucket = self._stack_bucket()
            if not bucket:
                return

        check_not_in_use(self._clients, bucket, model, revision, prefix)

        model_prefix = f"{prefix}{model}/{revision}/"
        resp = self._clients.s3.list_objects_v2(Bucket=bucket, Prefix=model_prefix)
        for obj in resp.get("Contents", []):
            self._clients.s3.delete_object(Bucket=bucket, Key=obj["Key"])

    def destroy(
        self,
        confirm: str,
        bucket: str | None = None,
    ) -> None:
        """Delete the cache: its objects, its bucket, and the managed stack.

        With an explicit ``bucket``, only that bucket is deleted; the managed
        cache stack is left alone.

        Parameters
        ----------
        confirm : str
            Must exactly match the bucket name to proceed.
        bucket : str | None
            S3 bucket name; if ``None``, uses the managed cache stack and its
            stack is deleted afterwards (waiting for completion).

        Raises
        ------
        ConfirmationError
            If ``confirm`` does not match the bucket name.
        CacheInUseError
            If any deployment exists or is being prepared.
        """
        managed = bucket is None
        if bucket is None:
            bucket = self._stack_bucket()
            if not bucket:
                return

        if confirm != bucket:
            raise ConfirmationError(
                f"confirmation {confirm!r} does not match bucket {bucket!r}; "
                f"pass --confirm {bucket}"
            )

        check_no_deployments(self._clients)

        resp = self._clients.s3.list_objects_v2(Bucket=bucket)
        for obj in resp.get("Contents", []):
            self._clients.s3.delete_object(Bucket=bucket, Key=obj["Key"])
        self._clients.s3.delete_bucket(Bucket=bucket)

        if managed:
            self._clients.cfn.delete_stack(StackName=_CACHE_STACK_NAME)
            waiter = self._clients.cfn.get_waiter("stack_delete_complete")
            waiter.wait(StackName=_CACHE_STACK_NAME)
