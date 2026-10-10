"""Count a request exactly as the model will see it (research R1).

ember counts with the loaded ``joint_schema_model.encode_record`` itself, with
truncation disabled, so the count includes the questions, schema, prompt wrapper,
and media, not just the state.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from .governing_limit import GoverningLimit
from .limit_source import LimitSource
from .limits import Limits

_MEDIA_KEYS = ("images", "videos")


@dataclass(frozen=True)
class RequestSize:
    """A request's encoded size and how it splits.

    Attributes
    ----------
    total : int
        Tokens in the full encoded request.
    state : int
        Tokens the state adds.
    media : int
        Tokens the images and video frames add.
    fixed : int
        Tokens with no state and no media: questions, schema, and prompt wrapper.
    """

    total: int
    state: int
    media: int
    fixed: int

    def __post_init__(self) -> None:
        """Check that the parts sum to the total."""
        if self.state + self.media + self.fixed != self.total:
            raise ValueError(
                f"request size parts do not sum to the total: state {self.state} "
                f"+ media {self.media} + fixed {self.fixed} != {self.total}"
            )


def measure(js: Any, processor: Any, request: dict[str, Any]) -> RequestSize:
    """Measure ``request`` with the loaded joint module's own encoder.

    The full request, the request without media, and a bare request (no state,
    no media) are each encoded with ``max_length=sys.maxsize``, so nothing is
    truncated. Text-only requests skip the no-media encode.

    Parameters
    ----------
    js : Any
        The loaded ``joint_schema_model`` module.
    processor : Any
        The model's processor; its ``tokenizer`` does the counting.
    request : dict[str, Any]
        The SystemOne request exactly as ``systemone`` will receive it.

    Returns
    -------
    RequestSize
        The untruncated total and its split into state, media, and fixed
        overhead.

    Raises
    ------
    RuntimeError
        If ``js`` has no ``encode_record``: the model does not fit ember's
        loader contract. Every other exception from ``encode_record``
        propagates unchanged.
    """
    encode = getattr(js, "encode_record", None)
    if encode is None:
        raise RuntimeError(
            "the loaded joint_schema_model has no encode_record, so ember cannot "
            "measure requests; the model does not fit ember's loader contract"
        )
    tokenizer = processor.tokenizer

    def length(record: dict[str, Any]) -> int:
        encoded = encode(tokenizer, record, max_length=sys.maxsize, processor=processor)
        return len(encoded.input_ids)

    total = length(request)
    text_only = {key: value for key, value in request.items() if key not in _MEDIA_KEYS}
    no_media = length(text_only) if len(text_only) < len(request) else total
    fixed = length({**text_only, "state": ""})
    return RequestSize(
        total=total, state=no_media - fixed, media=total - no_media, fixed=fixed
    )


def refusal_message(size: RequestSize, limits: Limits, declared: int | None) -> str:
    """Explain an over-limit refusal: the split, what to trim, and what can be raised.

    Parameters
    ----------
    size : RequestSize
        The refused request's measured size.
    limits : Limits
        The limits it exceeded.
    declared : int | None
        The model's declared maximum, or ``None`` when it is unknown.

    Returns
    -------
    str
        One ASCII line in the ``contracts/http-api.md`` format. It contains no
        slash or backslash, so the MCP layer forwards it to the agent unchanged.
    """
    limit = limits.enforced
    if limits.governing is GoverningLimit.CAP:
        name, setting = "per-request cap", "EMBER_MAX_REQUEST_LENGTH"
        hint = (
            "Operators can raise EMBER_MAX_REQUEST_LENGTH (0 removes the cap; "
            "the maximum length then applies)."
        )
    else:
        name, setting = "maximum length", "EMBER_MAX_LENGTH"
        if limits.max_length_source is not LimitSource.OPERATOR:
            hint = "This is the model's own maximum and cannot be raised."
        elif declared is None:
            hint = "Operators can raise EMBER_MAX_LENGTH."
        else:
            hint = (
                f"Operators can raise EMBER_MAX_LENGTH up to the model's "
                f"{declared} tokens."
            )
    if size.fixed > limit:
        advice = (
            "The questions alone exceed the limit: ask fewer or shorter "
            "questions, then retry."
        )
    else:
        advice = (
            "Reduce the largest part (shorten the state, attach fewer or smaller "
            "images or frames, or ask fewer questions), then retry."
        )
    return (
        f"request too large: {size.total} tokens exceeds the {limit}-token "
        f"{name} ({setting}). Split: state {size.state}, media {size.media}, "
        f"fixed overhead {size.fixed} (questions, schema, prompt wrapper). "
        f"{advice} {hint}"
    )
