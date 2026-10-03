"""Model registry + download lifecycle (pull / list / path / rm).

Weights live in HuggingFace's cache by default so they are shared with other HF
tools. A source checkout's ``.models/<dir>`` wins if present (dev convenience),
and ``CLEF_MODEL_DIR`` overrides everything.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import paths


@dataclass(frozen=True)
class ModelSpec:
    name: str
    repo: str
    dir_name: str
    params: str
    approx_bytes: int
    revision: str


REGISTRY: dict[str, ModelSpec] = {
    "flash": ModelSpec(
        "flash", "Cloudflare/clef-flash", "clef-flash", "9B", 18 * 2**30,
        revision="17f0b0ad64efb65d273590632833508766b2aae6",
    ),
    "full": ModelSpec(
        "full", "Cloudflare/clef", "clef", "27B", 55 * 2**30,
        revision="2f3de3dd85f379784083b0814d997ab627200f0c",
    ),
}
DEFAULT = "flash"


def get(name: str | None) -> ModelSpec:
    key = (name or DEFAULT).lower()
    if key not in REGISTRY:
        raise KeyError(f"unknown model {name!r}; choose from {', '.join(REGISTRY)}")
    return REGISTRY[key]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _dev_dir(spec: ModelSpec) -> Path:
    return _repo_root() / ".models" / spec.dir_name


def is_cached(name: str) -> bool:
    return resolve_dir(name) is not None


def resolve_dir(name: str | None = None) -> Path | None:
    """Return the local directory of a pulled model, or None if not present."""
    spec = get(name)
    override = os.environ.get("CLEF_MODEL_DIR")
    if override:
        path = Path(override)
        return path if path.is_dir() else None
    dev = _dev_dir(spec)
    if dev.is_dir():
        return dev
    try:
        from huggingface_hub import snapshot_download

        return Path(snapshot_download(spec.repo, revision=spec.revision, local_files_only=True))
    except Exception:
        return None


def _disk_ok(target: Path, required: int) -> tuple[bool, str]:
    try:
        free = shutil.disk_usage(target if target.exists() else target.parent).free
    except Exception:
        return True, ""
    if free < required * 1.15:
        return False, (
            f"low disk: need ~{required / 2**30:.0f} GB free, have {free / 2**30:.1f} GB"
        )
    return True, ""


def pull(name: str | None = None, allow_low_disk: bool = False) -> Path:
    """Download (or verify) a model's pinned revision into the HF cache."""
    spec = get(name)
    from huggingface_hub import snapshot_download

    ok, message = _disk_ok(paths.hf_hub_cache(), spec.approx_bytes)
    if not ok and not allow_low_disk:
        raise RuntimeError(f"{message} (re-run with --allow-low-disk to override)")
    return Path(snapshot_download(spec.repo, revision=spec.revision))


def size_on_disk(path: Path) -> int:
    total = 0
    for file in path.rglob("*"):
        try:
            if file.is_file():
                total += file.stat().st_size
        except OSError:
            pass
    return total


def list_models() -> list[dict]:
    rows = []
    for name, spec in REGISTRY.items():
        path = resolve_dir(name)
        rows.append(
            {
                "name": name,
                "repo": spec.repo,
                "params": spec.params,
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
        from huggingface_hub import scan_cache_dir

        cache = scan_cache_dir()
        revisions = [
            rev.commit_hash for repo in cache.repos if repo.repo_id == spec.repo for rev in repo.revisions
        ]
        if not revisions:
            return f"{spec.repo} is not cached"
        cache.delete_revisions(*revisions).execute()
        return f"removed {spec.repo} from HF cache"
    except Exception as exc:  # pragma: no cover - best effort
        return f"could not remove {spec.repo}: {exc}"
