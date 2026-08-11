"""The retryable-status set had no effect, and had drifted from the list that did.

`_RETRYABLE_HTTP` lists 429, 500, 502, 503, 504. It was referenced exactly once in the module —
its own definition. The decision was made by a separate list of strings containing "503", "502",
"504", "429" and *not* "500", so a provider raising a plain exception carrying "HTTP 500" was not
retried while every other 5xx was.
"""

from __future__ import annotations

import random

import pytest

from untell._retry import _RETRYABLE_HTTP, _is_retryable, retry


@pytest.mark.parametrize("code", sorted(_RETRYABLE_HTTP))
def test_every_code_in_the_set_is_actually_retried(code: int):
    assert _is_retryable(RuntimeError(f"server returned HTTP {code}"))


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_a_client_error_is_not_retried(code: int):
    """Retrying these burns the caller's budget on a request that will never succeed."""
    assert not _is_retryable(RuntimeError(f"server returned HTTP {code}"))


def test_named_exception_types_are_still_retried():
    class RateLimitError(Exception):
        pass

    assert _is_retryable(RateLimitError("slow down"))


def test_message_keywords_are_still_retried():
    for msg in ("rate limit exceeded", "service unavailable", "connection reset by peer"):
        assert _is_retryable(RuntimeError(msg)), msg


def test_an_ordinary_error_is_not_retried():
    assert not _is_retryable(ValueError("bad argument"))


def test_the_delay_never_exceeds_max_delay(monkeypatch: pytest.MonkeyPatch):
    """The cap is applied after the jitter. Adding it afterwards put the ceiling at max_delay + 1."""
    slept: list[float] = []
    monkeypatch.setattr("untell._retry.time.sleep", slept.append)
    calls = {"n": 0}

    def always_503():
        calls["n"] += 1
        raise RuntimeError("HTTP 503 service unavailable")

    with pytest.raises(RuntimeError):
        retry(always_503, max_attempts=6, base_delay=10.0, max_delay=12.0)

    assert calls["n"] == 6
    assert slept, "premise: it must have backed off"
    assert max(slept) <= 12.0, f"delays {slept} exceed the documented cap"


def test_retrying_does_not_disturb_the_callers_random_stream(monkeypatch: pytest.MonkeyPatch):
    """Jitter draws from a private generator; the global one belongs to the caller."""
    monkeypatch.setattr("untell._retry.time.sleep", lambda _s: None)

    def boom():
        raise RuntimeError("HTTP 503")

    random.seed(1234)
    expected = [random.random() for _ in range(3)]

    random.seed(1234)
    first = random.random()
    with pytest.raises(RuntimeError):
        retry(boom, max_attempts=4)
    rest = [random.random() for _ in range(2)]

    assert [first, *rest] == expected


def test_a_non_retryable_error_raises_immediately(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("untell._retry.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def bad_arg():
        calls["n"] += 1
        raise ValueError("bad argument")

    with pytest.raises(ValueError):
        retry(bad_arg, max_attempts=5)
    assert calls["n"] == 1, "a permanent error must not be retried"
