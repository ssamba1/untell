"""What counts as transient, checked against messages providers actually emit.

`_is_retryable` read status codes with a bare `\\b([1-5]\\d{2})\\b`, so any three-digit number in the
message made a permanent failure look transient. MEASURED against nine realistic non-retryable
messages, four were retried:

    invalid_request_error: max_tokens must be <= 500
    context length 502 tokens exceeds the 500 token limit
    ValueError: expected 429 items in the batch, got 12
    invalid parameter: timeout must be a positive number

The first three are configuration mistakes that fail identically on every attempt — three tries with
exponential backoff for an answer that cannot change. The last is worse: a bug in our own call,
masked by a retry.

Tightening it broke the other direction twice, which is why both are asserted here. Requiring a word
boundary before the keyword lost `HTTPError: 500` and `APIStatusError: 500`, where there is none;
requiring the code at the head of the message lost `(429) rate_limit_exceeded`.

And the tightening surfaced a gap in the code set itself: **529 Overloaded was absent**. That is
Anthropic's capacity code, on a package that ships an Anthropic rewriter — the provider whose
overload signal we would see most often was the one not retried. It was found by checking a real
message against the classifier, not by reading the set, which looks complete until asked about a
specific provider.
"""

from __future__ import annotations

import pytest

from untell._retry import _RETRYABLE_HTTP, _is_retryable, retry


class _Err(Exception):
    pass


TRANSIENT = [
    "HTTP 500 Internal Server Error",
    "status 503 Service Unavailable",
    "Error code: 429 rate limit reached",
    "502 Bad Gateway",
    "HTTPError: 500",
    "APIStatusError: 500 server error",
    "anthropic.APIStatusError: 529 overloaded",
    "HTTP 408 Request Timeout",
    "(429) rate_limit_exceeded",
    "[503] upstream unavailable",
    "error 504 gateway timeout",
    "Read timeout",
    "Request timed out after 30s",
    "Connection reset by peer",
    "Too many requests, try again later",
]

PERMANENT = [
    "400 Bad Request: invalid model",
    "401 Unauthorized",
    "403 Forbidden: no access to this model",
    "404 model not found",
    "BadRequestError: 400 unsupported parameter",
    "NotFoundError: 404 model claude-3 does not exist",
    "PermissionDeniedError: 403 your org lacks access",
    "AuthenticationError: incorrect api key provided",
    # The four that were retried before, and the reason this file exists.
    "invalid_request_error: max_tokens must be <= 500",
    "context length 502 tokens exceeds the 500 token limit",
    "ValueError: expected 429 items in the batch, got 12",
    "invalid parameter: timeout must be a positive number",
    "model gpt-4 supports 500 tokens per request",
]


@pytest.mark.parametrize("message", TRANSIENT, ids=lambda m: m[:30])
def test_a_transient_failure_is_retried(message: str) -> None:
    assert _is_retryable(_Err(message)) is True


@pytest.mark.parametrize("message", PERMANENT, ids=lambda m: m[:30])
def test_a_permanent_failure_is_not(message: str) -> None:
    assert _is_retryable(_Err(message)) is False


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError("timeout"),
        ConnectionError("connection failed"),
        ConnectionResetError("reset"),
        ConnectionAbortedError("aborted"),
        ConnectionRefusedError("refused"),
        BrokenPipeError("broken pipe"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_builtin_transient_exceptions_are_retried(exc: Exception) -> None:
    """Matched by TYPE, because the name set misses every subclass — and the subclasses are the
    ones actually raised.

    `ConnectionResetError`, `ConnectionAbortedError` and `ConnectionRefusedError` all inherit from
    `ConnectionError`, which IS in the name set, and none of them shares its name. MEASURED before
    the fix: the base class was retryable and all three subclasses were not, so the classifier's
    most-cited signal was matching a class nobody raises directly. `BrokenPipeError` was retried
    only because its default message happens to contain "broken pipe" — change the message and it
    stops.
    """
    assert _is_retryable(exc) is True


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("400 bad request"),
        KeyError("missing"),
        TypeError("bad type"),
        PermissionError("403 forbidden"),
        FileNotFoundError("404 no such file"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_builtin_permanent_exceptions_are_not(exc: Exception) -> None:
    """Guards the guard. `PermissionError` and `FileNotFoundError` are `OSError` subclasses, so a
    type check written one level too high would sweep them in."""
    assert _is_retryable(exc) is False


def test_anthropics_overload_code_is_in_the_set() -> None:
    """529 is not an IANA status and is easy to leave out of a list built from the standard ones.
    This package ships an Anthropic rewriter, so it is the code most likely to be seen."""
    assert 529 in _RETRYABLE_HTTP


def test_the_fixtures_exercise_both_answers() -> None:
    """Guards the guard: a classifier stuck on one answer would pass half this file, and a fixture
    list that drifted to one side would hide it."""
    assert len(TRANSIENT) >= 10 and len(PERMANENT) >= 10


def test_a_permanent_failure_is_raised_on_the_first_attempt() -> None:
    """The behaviour the classification is for. A wrong answer here costs seconds of backoff per
    call, multiplied by best-of-N draws across iterations."""
    calls = []

    def boom():
        calls.append(1)
        raise _Err("400 Bad Request: invalid model")

    with pytest.raises(_Err):
        retry(boom, max_attempts=3, base_delay=0.0)
    assert calls == [1], f"a permanent failure was attempted {len(calls)} times"


def test_a_transient_failure_is_attempted_again() -> None:
    """The other half — a classifier that refused everything would pass the test above."""
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise _Err("HTTP 503 Service Unavailable")
        return "ok"

    assert retry(flaky, max_attempts=3, base_delay=0.0) == "ok"
    assert len(calls) == 3
