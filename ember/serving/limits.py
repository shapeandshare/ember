"""Resolve the effective maximum, the per-request cap, and the enforced limit.

Torch-free, so the CLI (``ember doctor``) and the server share one resolver.
The rules are in ``specs/003-context-window-audit/contracts/config.md``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .. import models
from ..cfg import config
from .governing_limit import GoverningLimit
from .limit_source import LimitSource

_log = logging.getLogger(__name__)

#: Effective maximum used when a model's config.json declares none.
FALLBACK_MAX_LENGTH = 32768

#: Per-request cap used until a model's cap is measured.
FALLBACK_REQUEST_CAP = 32768

_MAX_LENGTH_SOURCES = frozenset(
    {LimitSource.MODEL, LimitSource.FALLBACK, LimitSource.OPERATOR}
)
_CAP_SOURCES = frozenset(
    {LimitSource.MEASURED, LimitSource.FALLBACK, LimitSource.OPERATOR}
)


class Limits(BaseModel):
    """The length limits a server enforces, each with its source.

    Attributes
    ----------
    max_length : int
        The effective maximum: the most tokens the model processes.
    max_length_source : LimitSource
        ``model``, ``fallback``, or ``operator``.
    max_request_length : int
        The per-request cap; ``0`` means the cap is disabled.
    max_request_length_source : LimitSource
        ``measured``, ``fallback``, or ``operator``; always ``operator`` when
        the cap is disabled.
    """

    model_config = ConfigDict(frozen=True)

    max_length: int = Field(ge=1)
    max_length_source: LimitSource
    max_request_length: int = Field(ge=0)
    max_request_length_source: LimitSource

    @model_validator(mode="after")
    def _check_sources(self) -> Limits:
        if self.max_length_source not in _MAX_LENGTH_SOURCES:
            raise ValueError(f"max_length cannot come from {self.max_length_source}")
        if self.max_request_length_source not in _CAP_SOURCES:
            raise ValueError(
                f"max_request_length cannot come from {self.max_request_length_source}"
            )
        if (
            self.max_request_length == 0
            and self.max_request_length_source is not LimitSource.OPERATOR
        ):
            raise ValueError("only an operator setting can disable the cap")
        return self

    @property
    def enforced(self) -> int:
        """The most tokens a request may encode to."""
        if self.max_request_length > 0:
            return min(self.max_request_length, self.max_length)
        return self.max_length

    @property
    def governing(self) -> GoverningLimit:
        """Which limit sets the enforced limit."""
        if 0 < self.max_request_length <= self.max_length:
            return GoverningLimit.CAP
        return GoverningLimit.MAXIMUM

    def summary(self) -> str:
        """Describe the limits on one line, as the load log and doctor print them.

        Returns
        -------
        str
            ``enforced {E} tokens; max_length {M} ({src}), max_request_length {C}
            ({src})``, with ``{C}`` as ``disabled`` when the cap is ``0``.
        """
        cap = str(self.max_request_length) if self.max_request_length else "disabled"
        return (
            f"enforced {self.enforced} tokens; "
            f"max_length {self.max_length} ({self.max_length_source}), "
            f"max_request_length {cap} ({self.max_request_length_source})"
        )


def declared_max_length(model_dir: str | os.PathLike[str]) -> int | None:
    """Return the maximum the model declares in its ``config.json``.

    Parameters
    ----------
    model_dir : str | os.PathLike[str]
        Directory containing the model's ``config.json``.

    Returns
    -------
    int | None
        ``text_config.max_position_embeddings`` (or the top-level value), or
        ``None`` when the file can't be read or declares no positive value.
    """
    try:
        loaded = json.loads((Path(model_dir) / "config.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    text = loaded.get("text_config")
    text = text if isinstance(text, dict) else {}
    value = text.get("max_position_embeddings") or loaded.get("max_position_embeddings")
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def model_max_length(model_dir: str | os.PathLike[str]) -> int:
    """Resolve the model's declared maximum, falling back when it is unknown.

    Parameters
    ----------
    model_dir : str | os.PathLike[str]
        Directory containing the model's ``config.json``.

    Returns
    -------
    int
        The declared maximum, or ``FALLBACK_MAX_LENGTH`` when ``config.json``
        can't be read or declares no positive value.
    """
    declared = declared_max_length(model_dir)
    return FALLBACK_MAX_LENGTH if declared is None else declared


def default_request_cap(registry_key: str | None) -> tuple[int, LimitSource]:
    """Return the per-request cap that applies when no operator sets one.

    Parameters
    ----------
    registry_key : str | None
        The loaded model's registry key, or ``None`` for a model outside the
        registry (``EMBER_MODEL_DIR`` or ``EMBER_MODEL_S3_URI``).

    Returns
    -------
    tuple[int, LimitSource]
        A registry model's measured cap (``measured``), or
        ``FALLBACK_REQUEST_CAP`` until it is measured (``fallback``). Outside
        the registry: the lowest measured registry cap, or
        ``FALLBACK_REQUEST_CAP`` when none is measured (``fallback`` either way).

    Raises
    ------
    KeyError
        If ``registry_key`` names no registry entry.
    """
    if registry_key is not None:
        measured = models.get(registry_key).max_request_length
        if measured is not None:
            return measured, LimitSource.MEASURED
        return FALLBACK_REQUEST_CAP, LimitSource.FALLBACK
    caps = [
        spec.max_request_length
        for spec in models.REGISTRY.values()
        if spec.max_request_length is not None
    ]
    return (min(caps) if caps else FALLBACK_REQUEST_CAP), LimitSource.FALLBACK


def _operator_value(name: str, raw: int | str | None) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool) or not isinstance(raw, int | str):
        _log.warning("ignoring %s=%r: not an integer", name, raw)
        return None
    try:
        value = int(raw)
    except ValueError:
        _log.warning("ignoring %s=%r: not an integer", name, raw)
        return None
    if value < 0:
        _log.warning("ignoring %s=%d: negative", name, value)
        return None
    return value


def resolve(
    declared: int | None,
    registry_key: str | None,
    *,
    max_length: int | str | None = None,
    max_request_length: int | str | None = None,
) -> Limits:
    """Resolve the limits a server enforces.

    Parameters
    ----------
    declared : int | None
        The model's declared maximum, or ``None`` when it is unknown.
    registry_key : str | None
        The loaded model's registry key, or ``None`` outside the registry.
    max_length : int | str | None, optional
        The operator's effective maximum. ``None``, ``0``, or an invalid value
        (logged) means unset. A value above a known ``declared`` is clamped to
        it, with a warning.
    max_request_length : int | str | None, optional
        The operator's per-request cap. ``None`` or an invalid value (logged)
        means unset; ``0`` disables the cap.

    Returns
    -------
    Limits
        The effective maximum and the per-request cap, each with its source.
    """
    operator_max = _operator_value("max_length", max_length)
    operator_cap = _operator_value("max_request_length", max_request_length)

    if not operator_max:
        if declared is None:
            length, length_source = FALLBACK_MAX_LENGTH, LimitSource.FALLBACK
        else:
            length, length_source = declared, LimitSource.MODEL
    elif declared is not None and operator_max > declared:
        _log.warning(
            "max_length %d is above the model's declared maximum %d; using %d",
            operator_max,
            declared,
            declared,
        )
        length, length_source = declared, LimitSource.MODEL
    else:
        length, length_source = operator_max, LimitSource.OPERATOR

    if operator_cap is None:
        cap, cap_source = default_request_cap(registry_key)
    else:
        cap, cap_source = operator_cap, LimitSource.OPERATOR

    return Limits(
        max_length=length,
        max_length_source=length_source,
        max_request_length=cap,
        max_request_length_source=cap_source,
    )


def from_config(
    model_dir: str | os.PathLike[str] | None, registry_key: str | None
) -> Limits:
    """Resolve the limits from the model's ``config.json`` and ember's config.

    Parameters
    ----------
    model_dir : str | os.PathLike[str] | None
        Directory containing the model's ``config.json``, or ``None`` when the
        model isn't pulled (its declared maximum is then unknown).
    registry_key : str | None
        The loaded model's registry key, or ``None`` outside the registry.

    Returns
    -------
    Limits
        ``resolve`` applied to the declared maximum and to ``max_length`` and
        ``max_request_length`` as configured (flag > env > config file >
        default); each may be an env string, an int, or ``None``.
    """
    return resolve(
        None if model_dir is None else declared_max_length(model_dir),
        registry_key,
        max_length=config.resolve("max_length"),
        max_request_length=config.resolve("max_request_length"),
    )
