"""CacheUploader: uploads model files to S3 and writes the manifest last."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .cache_file_helpers import is_allowed, sha256_file
from .cached_model import CachedFile, CachedModel


class CacheUploader:
    """Uploads model files to S3 and writes the manifest as the final object.

    Skips files whose size and ``x-amz-meta-sha256`` already match.  The
    manifest is always written last so a partial upload is detectable.

    Parameters
    ----------
    s3_client : Any
        A boto3 S3 client (or a mock with the same interface).
    """

    def __init__(self, s3_client: Any) -> None:
        self._s3 = s3_client

    def upload(
        self,
        model: str,
        revision: str,
        bucket: str,
        prefix: str,
        local_path: Path,
    ) -> None:
        """Upload all allowed files and write the manifest last.

        Parameters
        ----------
        model : str
            Registry key (e.g. ``"flash"``).
        revision : str
            Model revision.
        bucket : str
            S3 bucket name.
        prefix : str
            S3 key prefix (e.g. ``"models/"``).
        local_path : Path
            Local directory containing the downloaded model files.
        """
        from botocore.exceptions import ClientError  # import-placement:allow

        files_to_upload: list[Path] = sorted(
            p for p in local_path.rglob("*") if p.is_file() and is_allowed(p)
        )

        cached_files: list[CachedFile] = []
        total_bytes = 0

        for file_path in files_to_upload:
            rel_path = file_path.relative_to(local_path)
            s3_key = f"{prefix}{model}/{revision}/{rel_path}"
            file_size = file_path.stat().st_size
            file_sha256 = sha256_file(file_path)

            # Skip if already uploaded with matching size and sha256.
            try:
                head = self._s3.head_object(Bucket=bucket, Key=s3_key)
                existing_size = head.get("ContentLength", -1)
                existing_sha256 = head.get("Metadata", {}).get("sha256", "")
                if existing_size == file_size and existing_sha256 == file_sha256:
                    cached_files.append(
                        CachedFile(
                            path=str(rel_path),
                            size=file_size,
                            sha256=file_sha256,
                        )
                    )
                    total_bytes += file_size
                    continue
            except ClientError:
                pass

            # Upload the file.
            with file_path.open("rb") as fh:
                self._s3.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=fh.read(),
                    Metadata={"sha256": file_sha256},
                )
            cached_files.append(
                CachedFile(
                    path=str(rel_path),
                    size=file_size,
                    sha256=file_sha256,
                )
            )
            total_bytes += file_size

        # Write the manifest last.
        cached_model = CachedModel(
            model=model,
            revision=revision,
            s3_uri=f"s3://{bucket}/{prefix}{model}/{revision}",
            total_bytes=total_bytes,
            files=cached_files,
        )
        manifest_key = f"{prefix}{model}/{revision}/manifest.json"
        self._s3.put_object(
            Bucket=bucket,
            Key=manifest_key,
            Body=cached_model.model_dump_json().encode(),
            ContentType="application/json",
        )
