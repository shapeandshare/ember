"""A fake ``joint_schema_model`` for engine and request-size tests (no model load).

``encode_record`` returns a record whose ``input_ids`` length is a known function
of the record, so a test can predict exactly what ember measures.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

#: Fake token cost of one image or one video frame.
MEDIA_TOKENS = 7
#: Fake token cost of one question.
QUESTION_TOKENS = 3
#: Fake token cost of the prompt wrapper (prefix and suffix).
WRAPPER_TOKENS = 5

SystemOne = Callable[[Any, Any, dict[str, Any], int], dict[str, Any]]


def record_length(record: dict[str, Any]) -> int:
    """Return the fake encoded length of ``record``."""
    frames = len(record.get("images") or []) + sum(
        len(video) for video in record.get("videos") or []
    )
    return (
        len(str(record["state"]))
        + MEDIA_TOKENS * frames
        + QUESTION_TOKENS * len(record["questions"])
        + WRAPPER_TOKENS
    )


class FakeJointModule:
    """A joint module with ``encode_record`` and ``systemone`` and no model.

    The default ``systemone`` answers nothing and reports ``usage.input_tokens``
    as the encoded length cut to ``max_length``, the way upstream truncates, so a
    test can tell a full-length call from a shortened one.
    """

    def __init__(
        self,
        systemone: SystemOne | None = None,
        encode_error: Exception | None = None,
    ) -> None:
        self.encode_calls: list[dict[str, Any]] = []
        self.systemone_calls: list[dict[str, Any]] = []
        self._systemone = systemone
        self._encode_error = encode_error

    def encode_record(
        self,
        tokenizer: Any,
        record: dict[str, Any],
        max_length: int = 16384,
        max_state_tokens: int | None = None,
        processor: Any | None = None,
    ) -> SimpleNamespace:
        self.encode_calls.append(
            {
                "tokenizer": tokenizer,
                "record": record,
                "max_length": max_length,
                "processor": processor,
            }
        )
        if self._encode_error is not None:
            raise self._encode_error
        return SimpleNamespace(input_ids=tuple(range(record_length(record))))

    def systemone(
        self,
        model: Any,
        processor: Any,
        request: dict[str, Any],
        max_length: int = 16384,
    ) -> dict[str, Any]:
        self.systemone_calls.append({"request": request, "max_length": max_length})
        if self._systemone is not None:
            return self._systemone(model, processor, request, max_length)
        return {
            "model": request["model"],
            "answers": {},
            "usage": {
                "input_tokens": min(record_length(request), max_length),
                "output_tokens": 0,
            },
        }
