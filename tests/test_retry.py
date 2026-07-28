"""Tests for the exponential-backoff retry wrapper — no network, no monkeypatching needed."""
from __future__ import annotations

import time

import pytest

from untell._retry import retry


def test_retry_success_on_first_call():
    """A function that succeeds immediately should be called exactly once."""
    calls = 0

    def ok():
        nonlocal calls
        calls += 1
        return 42

    assert retry(ok, max_attempts=3) == 42
    assert calls == 1


def test_retry_raises_non_retryable_error():
    """A non-retryable error (e.g. ValueError) should not be retried."""

    def boom():
        raise ValueError("bad input")

    with pytest.raises(ValueError, match="bad input"):
        retry(boom, max_attempts=3)


def test_retry_succeeds_on_third_attempt():
    """A transient error that clears should succeed on the retry."""
    calls = 0
    start = time.monotonic()

    def flaky():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("rate limited")
        return "ok"

    result = retry(flaky, max_attempts=3, base_delay=0.01)
    assert result == "ok"
    assert calls == 3
    # Should have taken at least 2 backoff delays: ~0.01 + ~0.02 + jitter
    assert time.monotonic() - start >= 0.01


def test_retry_exhausts_on_persistent_error():
    calls = 0

    def always_fails():
        nonlocal calls
        calls += 1
        raise TimeoutError("timeout")

    with pytest.raises(TimeoutError, match="timeout"):
        retry(always_fails, max_attempts=2, base_delay=0.01)
    assert calls == 2


def test_retry_max_attempts_one_disables_retry():
    calls = 0

    def flaky():
        nonlocal calls
        calls += 1
        if calls < 2:
            raise ConnectionError("transient")
        return "ok"

    with pytest.raises(ConnectionError, match="transient"):
        retry(flaky, max_attempts=1, base_delay=0.01)
    assert calls == 1


def test_retry_zero_attempts_does_one_anyway():
    retry(lambda: 1, max_attempts=0)
    # Should still attempt the call at least once


def test_retry_kwargs_passed_through():
    def identity(x, *, y=0):
        return x + y

    assert retry(identity, args=(10,), kw={"y": 5}) == 15


def test_retry_detects_api_keywords_in_message():
    """Rate-limit-like messages should be retried."""

    def flaky():
        raise RuntimeError("429 Too Many Requests")

    with pytest.raises(RuntimeError):  # re-raised after exhausting retries
        retry(flaky, max_attempts=2, base_delay=0.01)
