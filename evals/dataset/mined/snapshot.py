"""VaultSnapshot: read a vault tree at a pinned git commit, read-only."""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterator
from pathlib import Path

from .snapshot_file import SnapshotFile


class VaultSnapshotError(RuntimeError):
    """A pinned revision cannot be read (missing commit or path)."""


class VaultSnapshot:
    """Read ``<subdir>`` from a committed revision without touching the checkout.

    Parameters
    ----------
    repo : Path
        The git repository root.
    commit : str
        The revision to read (the pin).
    subdir : str, optional
        The vault directory inside the repository.
    """

    def __init__(self, repo: Path, commit: str, subdir: str = "docs/vault") -> None:
        self._repo = repo
        self.commit = commit
        self._subdir = subdir

    def _git(self, *args: str) -> bytes:
        try:
            result = subprocess.run(  # noqa: S603 - fixed git argv
                ["git", "-C", str(self._repo), *args],  # noqa: S607 - system git
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode("utf-8", "replace").strip()
            raise VaultSnapshotError(
                f"cannot read {self.commit} in {self._repo}: {detail or 'git failed'}"
            ) from exc
        return result.stdout

    def _blobs(self) -> list[tuple[str, str]]:
        # -z: raw NUL-delimited paths; without it git C-quotes em-dash names.
        listing = self._git(
            "ls-tree", "-r", "-z", self.commit, "--", self._subdir
        ).decode("utf-8")
        blobs: list[tuple[str, str]] = []
        for entry in listing.split("\0"):
            if not entry:
                continue
            meta, _, path = entry.partition("\t")
            parts = meta.split()
            if len(parts) < 3 or parts[1] != "blob":
                continue
            blobs.append((path.removeprefix(f"{self._subdir}/"), parts[2]))
        return sorted(blobs)

    def require(self) -> VaultSnapshot:
        """Return self, raising when the pinned commit is absent."""
        self._git("cat-file", "-e", f"{self.commit}^{{commit}}")
        return self

    def read(self, path: str) -> str:
        """Return one vault file's committed text."""
        return self._read_text(f"{self.commit}:{self._subdir}/{path}")

    def read_file(self, path: str) -> str:
        """Return any repository file's committed text, relative to the root."""
        return self._read_text(f"{self.commit}:{path}")

    def _read_text(self, spec: str) -> str:
        try:
            return self._git("show", spec).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise VaultSnapshotError(f"{spec} is not UTF-8 text") from exc

    def files(self) -> Iterator[SnapshotFile]:
        """Yield every UTF-8 text file in the vault, sorted by path."""
        for relative, _ in self._blobs():
            try:
                text = self.read(relative)
            except VaultSnapshotError:
                continue
            yield SnapshotFile(path=relative, text=text)

    def tree_digest(self) -> str:
        r"""Return a sha256 over the sorted ``path\0<blob sha>`` pairs."""
        digest = hashlib.sha256()
        for relative, sha in self._blobs():
            digest.update(f"{relative}\0{sha}\n".encode())
        return digest.hexdigest()
