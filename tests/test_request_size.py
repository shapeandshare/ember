"""Unit tests for ember.serving.request_size: exact request counting (no model)."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from ember.serving.limit_source import LimitSource
from ember.serving.limits import Limits
from ember.serving.request_size import RequestSize, measure, refusal_message

from tests.fake_joint import (
    MEDIA_TOKENS,
    QUESTION_TOKENS,
    WRAPPER_TOKENS,
    FakeJointModule,
)

PROCESSOR = SimpleNamespace(tokenizer=object())
QUESTIONS = {
    "urgent": {"type": "noul"},
    "team": {"type": "choice", "criteria": {"db": "database", "web": "frontend"}},
}
STATE = "abcdefghij"
FIXED = QUESTION_TOKENS * len(QUESTIONS) + WRAPPER_TOKENS


def _request(**extra: object) -> dict:
    return {"model": "clef-flash", "state": STATE, "questions": QUESTIONS, **extra}


# ###########################################################################
# (a) the split and its invariant
# ###########################################################################
def test_a_text_request_splits_into_state_and_fixed_overhead():
    size = measure(FakeJointModule(), PROCESSOR, _request())
    assert size == RequestSize(
        total=len(STATE) + FIXED, state=len(STATE), media=0, fixed=FIXED
    )


def test_images_and_video_frames_count_as_media():
    request = _request(images=["i1", "i2"], videos=[["f1", "f2", "f3"]])
    size = measure(FakeJointModule(), PROCESSOR, request)
    assert size == RequestSize(
        total=len(STATE) + MEDIA_TOKENS * 5 + FIXED,
        state=len(STATE),
        media=MEDIA_TOKENS * 5,
        fixed=FIXED,
    )


def test_the_parts_sum_to_the_total():
    size = measure(FakeJointModule(), PROCESSOR, _request(images=["i1"]))
    assert size.state + size.media + size.fixed == size.total


def test_request_size_rejects_parts_that_do_not_sum_to_the_total():
    with pytest.raises(ValueError, match="sum"):
        RequestSize(total=10, state=3, media=3, fixed=3)


# ###########################################################################
# (b)-(d) how measure calls encode_record
# ###########################################################################
def test_every_encode_call_disables_truncation():
    js = FakeJointModule()
    measure(js, PROCESSOR, _request(images=["i1"]))
    assert [call["max_length"] for call in js.encode_calls] == [sys.maxsize] * 3


def test_encode_calls_get_the_processor_tokenizer_and_the_processor():
    js = FakeJointModule()
    measure(js, PROCESSOR, _request())
    assert all(call["tokenizer"] is PROCESSOR.tokenizer for call in js.encode_calls)
    assert all(call["processor"] is PROCESSOR for call in js.encode_calls)


def test_a_text_request_encodes_twice():
    js = FakeJointModule()
    measure(js, PROCESSOR, _request())
    assert len(js.encode_calls) == 2


def test_a_media_request_encodes_three_times():
    js = FakeJointModule()
    measure(js, PROCESSOR, _request(videos=[["f1"]]))
    assert len(js.encode_calls) == 3


def test_the_first_encode_is_the_request_as_sent():
    js = FakeJointModule()
    request = _request(images=["i1"])
    measure(js, PROCESSOR, request)
    assert js.encode_calls[0]["record"] == request


def test_the_no_media_encode_keeps_the_state_and_drops_the_media():
    js = FakeJointModule()
    measure(js, PROCESSOR, _request(images=["i1"], videos=[["f1"]]))
    no_media = js.encode_calls[1]["record"]
    assert no_media == _request()


def test_the_bare_encode_has_no_state_and_no_media():
    js = FakeJointModule()
    measure(js, PROCESSOR, _request(images=["i1"], videos=[["f1"]]))
    bare = js.encode_calls[-1]["record"]
    assert bare["state"] == ""
    assert "images" not in bare
    assert "videos" not in bare
    assert bare["questions"] == QUESTIONS


def test_measure_does_not_modify_the_request():
    request = _request(images=["i1"])
    measure(FakeJointModule(), PROCESSOR, request)
    assert request == _request(images=["i1"])


# ###########################################################################
# (e)-(f) errors
# ###########################################################################
def test_a_joint_module_without_encode_record_is_a_loader_contract_error():
    js = SimpleNamespace(systemone=lambda *a, **kw: {})
    with pytest.raises(RuntimeError, match="encode_record"):
        measure(js, PROCESSOR, _request())


@pytest.mark.parametrize(
    "error",
    [KeyError("state"), TypeError("bad"), AttributeError("bad"), ValueError("bad")],
)
def test_encode_errors_propagate_unchanged(error):
    js = FakeJointModule(encode_error=error)
    with pytest.raises(type(error)) as excinfo:
        measure(js, PROCESSOR, _request())
    assert excinfo.value is error


# ###########################################################################
# refusal_message (contracts/http-api.md)
# ###########################################################################
DECLARED = 262144
CONTRACT_SIZE = RequestSize(total=41230, state=39800, media=0, fixed=1430)
CONTRACT_EXAMPLE = (
    "request too large: 41230 tokens exceeds the 32768-token per-request cap "
    "(EMBER_MAX_REQUEST_LENGTH). Split: state 39800, media 0, fixed overhead 1430 "
    "(questions, schema, prompt wrapper). Reduce the largest part (shorten the "
    "state, attach fewer or smaller images or frames, or ask fewer questions), then "
    "retry. Operators can raise EMBER_MAX_REQUEST_LENGTH (0 removes the cap; the "
    "maximum length then applies)."
)


def _caps(
    max_length: int = DECLARED,
    max_length_source: LimitSource = LimitSource.MODEL,
    cap: int = 32768,
    cap_source: LimitSource = LimitSource.FALLBACK,
) -> Limits:
    return Limits(
        max_length=max_length,
        max_length_source=max_length_source,
        max_request_length=cap,
        max_request_length_source=cap_source,
    )


def test_the_refusal_matches_the_contract_example():
    assert refusal_message(CONTRACT_SIZE, _caps(), DECLARED) == CONTRACT_EXAMPLE


def test_the_refusal_keeps_the_prefix_clients_match():
    message = refusal_message(CONTRACT_SIZE, _caps(), DECLARED)
    assert message.startswith("request too large: 41230 tokens exceeds the 32768-token")


def test_the_refusal_shows_the_media_share():
    size = RequestSize(total=40000, state=100, media=38470, fixed=1430)
    message = refusal_message(size, _caps(), DECLARED)
    assert "Split: state 100, media 38470, fixed overhead 1430" in message


def test_a_lowered_maximum_names_ember_max_length_and_the_declared_maximum():
    size = RequestSize(total=2000, state=1500, media=0, fixed=500)
    limits = _caps(1024, LimitSource.OPERATOR, 0, LimitSource.OPERATOR)
    message = refusal_message(size, limits, DECLARED)
    assert "exceeds the 1024-token maximum length (EMBER_MAX_LENGTH)." in message
    assert message.endswith(
        "Operators can raise EMBER_MAX_LENGTH up to the model's 262144 tokens."
    )


def test_a_lowered_maximum_with_an_unknown_declared_maximum():
    size = RequestSize(total=2000, state=1500, media=0, fixed=500)
    limits = _caps(1024, LimitSource.OPERATOR, 0, LimitSource.OPERATOR)
    message = refusal_message(size, limits, None)
    assert message.endswith("Operators can raise EMBER_MAX_LENGTH.")


def test_the_models_own_maximum_cannot_be_raised():
    size = RequestSize(total=300000, state=298570, media=0, fixed=1430)
    limits = _caps(DECLARED, LimitSource.MODEL, 0, LimitSource.OPERATOR)
    message = refusal_message(size, limits, DECLARED)
    assert "exceeds the 262144-token maximum length (EMBER_MAX_LENGTH)." in message
    assert message.endswith("This is the model's own maximum and cannot be raised.")


def test_an_operator_maximum_at_the_declared_maximum_cannot_be_raised():
    size = RequestSize(total=300000, state=298570, media=0, fixed=1430)
    limits = _caps(DECLARED, LimitSource.OPERATOR, 0, LimitSource.OPERATOR)
    message = refusal_message(size, limits, DECLARED)
    assert message.endswith("This is the model's own maximum and cannot be raised.")


def test_a_fallback_maximum_can_be_raised_by_an_operator():
    size = RequestSize(total=40000, state=38570, media=0, fixed=1430)
    limits = _caps(32768, LimitSource.FALLBACK, 0, LimitSource.OPERATOR)
    message = refusal_message(size, limits, None)
    assert "exceeds the 32768-token maximum length (EMBER_MAX_LENGTH)." in message
    assert message.endswith("Operators can raise EMBER_MAX_LENGTH.")


def test_a_cap_above_the_maximum_lets_the_maximum_govern():
    size = RequestSize(total=20000, state=18570, media=0, fixed=1430)
    message = refusal_message(size, _caps(max_length=16384), 16384)
    assert "exceeds the 16384-token maximum length (EMBER_MAX_LENGTH)." in message


def test_the_questions_alone_can_exceed_the_limit():
    size = RequestSize(total=3000, state=10, media=0, fixed=2990)
    message = refusal_message(
        size, _caps(cap=2048, cap_source=LimitSource.OPERATOR), DECLARED
    )
    assert (
        "The questions alone exceed the limit: ask fewer or shorter questions, "
        "then retry." in message
    )
    assert "Reduce the largest part" not in message


@pytest.mark.parametrize(
    ("size", "limits"),
    [
        (CONTRACT_SIZE, _caps()),
        (
            RequestSize(total=9999999, state=9999000, media=0, fixed=999),
            _caps(cap=32768, cap_source=LimitSource.OPERATOR),
        ),
        (
            RequestSize(total=9999999, state=10, media=9997000, fixed=2989),
            _caps(1024, LimitSource.OPERATOR, 0, LimitSource.OPERATOR),
        ),
        (
            RequestSize(total=9999999, state=10, media=0, fixed=9999989),
            _caps(DECLARED, LimitSource.FALLBACK, 0, LimitSource.OPERATOR),
        ),
    ],
)
def test_the_refusal_survives_the_mcp_layer(size, limits):
    message = refusal_message(size, limits, DECLARED)
    assert "/" not in message
    assert "\\" not in message
    assert message.isascii()
    assert len(message) <= 600
