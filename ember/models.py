"""Model registry + download lifecycle (pull / list / path / rm).

Weights live in HuggingFace's cache by default so they are shared with other HF
tools. A source checkout's ``.models/<dir>`` wins if present (dev convenience),
and ``EMBER_MODEL_DIR`` overrides everything.

A hosted deployment that supplies its own S3 model location does not use this
registry at all — see ``EMBER_MODEL_S3_URI`` / :mod:`ember.serving.hosted`,
which resolves and loads a model directly from that URI, independent of
``REGISTRY``.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cfg import paths


@dataclass(frozen=True)
class ModelSpec:
    """A decision model's registry entry.

    Constitution Article V ("Model Loading"): ember supports any model that
    can run under its loader contract, not a hand-maintained allowlist of
    individually hash-verified weights. A ``ModelSpec`` is a directory entry
    (name, Hugging Face repo, size) for discoverability and
    ``pull``/``list``/``rm`` — not a security gate; no field here is used for
    integrity verification.

    Attributes
    ----------
    name : str
        Short key used in the CLI and config (e.g. ``"flash"``).
    repo : str
        Hugging Face Hub repo id (e.g. ``"Cloudflare/clef-flash"``).
    dir_name : str
        Directory name under a checkout's ``.models/``.
    params : str
        Human-readable parameter count (e.g. ``"9B"``).
    approx_bytes : int
        Approximate on-disk size of the pulled weights, in bytes.
    revision : str | None
        Optional Hugging Face Hub commit/branch/tag to download — a
        convenience for targeting a specific known-good version, not a
        verified pin. ``None`` fetches the repo's default branch.
    kind : str
        Model category. ``"decision"`` for the Clef models, which score typed
        questions instead of generating text. More categories can be added as
        ember grows beyond decision models.
    """

    name: str
    repo: str
    dir_name: str
    params: str
    approx_bytes: int
    revision: str | None = None
    kind: str = "decision"


REGISTRY: dict[str, ModelSpec] = {
    "flash": ModelSpec(
        "flash",
        "Cloudflare/clef-flash",
        "clef-flash",
        "9B",
        18 * 2**30,
        revision="17f0b0ad64efb65d273590632833508766b2aae6",
    ),
    "full": ModelSpec(
        "full",
        "Cloudflare/clef",
        "clef",
        "27B",
        55 * 2**30,
        revision="2f3de3dd85f379784083b0814d997ab627200f0c",
    ),
}
DEFAULT = "flash"


def get(name: str | None) -> ModelSpec:
    """Look up a model's registry entry by name.

    Parameters
    ----------
    name : str | None
        Model key (case-insensitive); ``None`` resolves to ``DEFAULT``.

    Returns
    -------
    ModelSpec
        The matching registry entry.

    Raises
    ------
    KeyError
        If ``name`` does not match any key in ``REGISTRY``.
    """
    key = (name or DEFAULT).lower()
    if key not in REGISTRY:
        raise KeyError(f"unknown model {name!r}; choose from {', '.join(REGISTRY)}")
    return REGISTRY[key]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _dev_dir(spec: ModelSpec) -> Path:
    return _repo_root() / ".models" / spec.dir_name


def resolve_dir(name: str | None = None, *, override: bool = True) -> Path | None:
    """Return the local directory to run a model from, or None if it is not present.

    ``EMBER_MODEL_DIR`` (when ``override`` is true) names the directory for the
    model being run; otherwise a checkout's ``.models/<dir>`` wins, then the
    Hugging Face Hub cache.
    """
    spec = get(name)
    env_dir = os.environ.get("EMBER_MODEL_DIR")
    if override and env_dir:
        path = Path(env_dir)
        return path if path.is_dir() else None
    dev = _dev_dir(spec)
    if dev.is_dir():
        return dev
    try:
        # import-placement:allow - avoids HF import at module load; local cache probe
        from huggingface_hub import snapshot_download

        return Path(
            snapshot_download(spec.repo, revision=spec.revision, local_files_only=True)
        )
    except Exception:
        return None


def _disk_ok(target: Path, required: int) -> tuple[bool, str]:
    try:
        free = shutil.disk_usage(target if target.exists() else target.parent).free
    except Exception:
        return True, ""
    if free < required * 1.15:
        return False, (
            f"low disk: need ~{required / 2**30:.0f} GB free, "
            f"have {free / 2**30:.1f} GB"
        )
    return True, ""


def pull(name: str | None = None, allow_low_disk: bool = False) -> Path:
    """Download a model into its local cache (or return it if already present)."""
    spec = get(name)
    dev = _dev_dir(spec)
    if dev.is_dir():
        return dev
    # import-placement:allow - deferred to pull(); avoids HF import at module load
    from huggingface_hub import snapshot_download

    ok, message = _disk_ok(paths.hf_hub_cache(), spec.approx_bytes)
    if not ok and not allow_low_disk:
        raise RuntimeError(f"{message} (re-run with --allow-low-disk to override)")
    return Path(snapshot_download(spec.repo, revision=spec.revision))


def size_on_disk(path: Path) -> int:
    """Sum the byte size of every regular file under a directory, recursively.

    Parameters
    ----------
    path : Path
        Directory to walk.

    Returns
    -------
    int
        Total size in bytes of all regular files under ``path``. Files that
        raise ``OSError`` while being stat'd are skipped.
    """
    total = 0
    for file in path.rglob("*"):
        try:
            if file.is_file():
                total += file.stat().st_size
        except OSError:
            pass
    return total


def list_models() -> list[dict[str, Any]]:
    """List every registered model with its cache status and size.

    Returns
    -------
    list[dict[str, Any]]
        One row per entry in ``REGISTRY``, with ``name``, ``repo``,
        ``params``, ``default``, ``cached``, ``path``, and ``bytes`` keys.
    """
    rows = []
    for name, spec in REGISTRY.items():
        path = resolve_dir(name, override=False)
        rows.append(
            {
                "name": name,
                "repo": spec.repo,
                "params": spec.params,
                "kind": spec.kind,
                "default": name == DEFAULT,
                "cached": path is not None,
                "path": str(path) if path else None,
                "bytes": size_on_disk(path) if path else 0,
            }
        )
    return rows


def remove(name: str | None = None) -> str:
    """Delete a model's local files. Returns a human-readable description."""
    spec = get(name)
    dev = _dev_dir(spec)
    if dev.is_dir():
        shutil.rmtree(dev)
        return f"removed {dev}"
    try:
        # import-placement:allow - deferred to remove(); avoids HF import at module load
        from huggingface_hub import scan_cache_dir

        cache = scan_cache_dir()
        revisions = [
            rev.commit_hash
            for repo in cache.repos
            if repo.repo_id == spec.repo
            for rev in repo.revisions
        ]
        if not revisions:
            return f"{spec.repo} is not cached"
        cache.delete_revisions(*revisions).execute()
        return f"removed {spec.repo} from HF cache"
    except Exception as exc:  # pragma: no cover - best effort
        return f"could not remove {spec.repo}: {exc}"
