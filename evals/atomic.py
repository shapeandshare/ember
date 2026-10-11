"""Atomic file writes: a sibling ``.tmp`` then ``os.replace`` (Article X §10.14).

A leaf module with no ``evals`` imports, so the dataset tooling, the harness,
and the report exporter can all share it without import cycles.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def write_atomic(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via a sibling ``.tmp`` and ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def copy_atomic(source: Path, target: Path) -> None:
    """Copy ``source`` to ``target`` via a sibling ``.tmp`` and ``os.replace``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, target)
