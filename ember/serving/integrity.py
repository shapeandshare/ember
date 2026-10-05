"""Model-directory integrity verification (E-001, T-001, T-002, S-002).

Verifies structural completeness and cryptographic integrity of a model directory
before any code from that directory is imported or executed.

Security properties enforced:
- T-002: structural check — required files must be present before load.
- E-001/T-001: ``joint_schema_model.py`` SHA-256 always verified; mismatch raises.
- S-002: ``joint_head.safetensors`` SHA-256 verified; mismatch raises for official
  model directories, warns for custom directories (``EMBER_MODEL_DIR`` pointing to
  a non-registry path — custom model heads must keep working per README).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from ..models import ModelSpec

log = logging.getLogger(__name__)

#: Files that must be present in every model directory before load.
_REQUIRED_FILES = (
    "config.json",
    "joint_schema_model.py",
    "joint_head.safetensors",
    "joint_head_config.json",
    "model.safetensors.index.json",
)


def _sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file in streaming 64 KiB chunks.

    Parameters
    ----------
    path : Path
        File to hash.

    Returns
    -------
    str
        Lowercase hex digest string (64 characters).
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_model_dir(
    model_dir: Path,
    spec: ModelSpec,
    *,
    official: bool,
) -> None:
    """Verify structural completeness and file integrity of a model directory.

    Called before ``joint_schema_model.py`` is imported and before
    ``joint_head.safetensors`` is loaded, so a tampered or incomplete directory
    is rejected before any executable model code runs.

    Parameters
    ----------
    model_dir : Path
        Resolved local model directory to verify.
    spec : ModelSpec
        Registry entry supplying the pinned SHA-256 hashes.
    official : bool
        ``True`` when ``model_dir`` is a registry-managed path (checkout
        ``.models/<dir>`` or HF cache at the pinned revision).  ``False`` for
        a custom directory supplied via ``EMBER_MODEL_DIR``.

        - Schema hash mismatch always raises regardless of this flag.
        - Head hash mismatch raises when ``official=True``; warns when
          ``official=False`` so custom model heads keep working.

    Raises
    ------
    RuntimeError
        If any required file is missing, the schema hash does not match, or
        (when ``official=True``) the head hash does not match.
    """
    # T-002: structural check
    for name in _REQUIRED_FILES:
        if not (model_dir / name).is_file():
            raise RuntimeError(
                f"model directory {model_dir} is missing required file {name!r}. "
                f"Re-pull the model: ember model pull"
            )

    # E-001 / T-001: schema integrity — always enforced
    schema_path = model_dir / "joint_schema_model.py"
    actual_schema = _sha256_file(schema_path)
    if actual_schema != spec.schema_sha256:
        raise RuntimeError(
            f"integrity check failed for joint_schema_model.py in {model_dir}.\n"
            f"  expected: {spec.schema_sha256[:16]}…\n"
            f"  actual:   {actual_schema[:16]}…\n"
            f"The file may have been tampered with. Re-pull the model: "
            f"ember model pull {spec.name}"
        )

    # S-002: head integrity — raise for official dirs, warn for custom dirs
    head_path = model_dir / "joint_head.safetensors"
    actual_head = _sha256_file(head_path)
    if actual_head != spec.head_sha256:
        if official:
            raise RuntimeError(
                f"integrity check failed for joint_head.safetensors in {model_dir}.\n"
                f"  expected: {spec.head_sha256[:16]}…\n"
                f"  actual:   {actual_head[:16]}…\n"
                f"The file may have been tampered with. Re-pull the model: "
                f"ember model pull {spec.name}"
            )
        log.warning(
            "joint_head.safetensors in %s does not match the pinned hash for %r "
            "(expected %s…, got %s…). Proceeding with custom model head.",
            model_dir,
            spec.name,
            spec.head_sha256[:16],
            actual_head[:16],
        )
