"""Killing tests for the _retry.py survivors found by the L2 mutation hunt.

Four of the five mutations survive the existing suite:

  L35  _RETRYABLE_HTTP {408, ...} -> {409, ...}
       The existing "HTTP 408 Request Timeout" fixture passes via the
       "request timeout" phrase even when 408 is removed from the set, so a
       bare status message is needed to pin the code itself.

  L103 _RETRYABLE_ERRS name check -> False
       Every existing name-set case is also caught by type or message, so a
       class whose NAME is in the set and nothing else is needed.

  L119 max_attempts: int = 3 -> 4
       Every existing test passes max_attempts explicitly, so the default is
       pinned by nothing. A function that succeeds on exactly the 4th call
       distinguishes 3 attempts from 4.

  L141 base_delay * (2 ** (attempt - 1)) -> 3 ** ...
       No test measures the backoff sequence; the existing ones only assert
       that SOME delay happened.

The fifth (L128, `< 1` -> `<= 1` on the max_attempts clamp) is an equivalent
mutation: both forms yield max_attempts == 1 for 0, 1 and negatives, and both
keep any larger value, so no behavioral test can distinguish them.
"""
from __future__ import annotations

import pytest

import untell._retry as r
from untell._retry import _is_retryable, retry


class _Err(Exception):
    pass


def test_a_bare_408_status_is_retryable() -> None:
    """Pin 408 in _RETRYABLE_HTTP itself, not via the timeout-phrase path.

    The existing fixture "HTTP 408 Request Timeout" stays green when 408 is
    removed from the set because "request timeout" is itself a retry signal.
    A bare "HTTP 408" has no phrase to fall back on.
    """
    assert _is_retryable(_Err("HTTP 408")) is True


def test_an_sdk_exception_name_is_retryable_even_with_no_signal_in_the_message() -> None:
    """Pin the name-set branch: SDK classes cannot be imported here, so the
    classifier must recognise them by type name alone.

    A locally defined class named `RateLimitError` inherits only Exception
    (not ConnectionError/TimeoutError) and its message contains no keyword,
    so only the `name in _RETRYABLE_ERRS` line can return True.
    """

    class RateLimitError(Exception):
        pass

    assert _is_retryable(RateLimitError("no signal in this message")) is True


def test_the_default_is_three_attempts() -> None:
    """Pin max_attempts=3 as the DEFAULT, not just as an explicit argument.

    Every other test passes max_attempts explicitly, so the default could
    drift to 4 (or anywhere) unnoticed. A function that clears on the 4th
    call succeeds under a 4-attempt default and raises under the shipped 3.
    """
    calls = []

    def clears_on_fourth():
        calls.append(1)
        if len(calls) < 4:
            raise ConnectionError("transient")
        return "ok"

    with pytest.raises(ConnectionError):
        retry(clears_on_fourth, base_delay=0.0)
    assert len(calls) == 3, f"default max_attempts ran {len(calls)} times, expected 3"


def test_backoff_doubles_each_attempt(monkeypatch) -> None:
    """Pin the exponential shape: base, 2x, 4x — not 3x, 9x.

    The existing tests assert only that *some* sleep happened. Record the
    actual delays with jitter fixed at zero so the sequence is exact.
    """
    sleeps: list[float] = []

    class _NoJitter:
        @staticmethod
        def random() -> float:
            return 0.0

    monkeypatch.setattr(r, "_JITTER", _NoJitter())
    monkeypatch.setattr(r.time, "sleep", lambda s: sleeps.append(s))

    calls = []

    def flaky():
        calls.append(1)
        raise ConnectionError("transient")

    with pytest.raises(ConnectionError):
        retry(flaky, max_attempts=4, base_delay=1.0, max_delay=100.0)

    assert sleeps == [1.0, 2.0, 4.0], f"backoff sequence was {sleeps}, expected [1.0, 2.0, 4.0]"


def test_the_clamp_accepts_one() -> None:
    """The clamp at max_attempts=1 is a no-op; the boundary value must pass.

    Pins that `max_attempts=1` runs exactly one attempt and raises on the
    first failure. (This is the boundary the `< 1` / `<= 1` mutation blurs —
    kept here as documentation of the intended semantics; the mutation is
    behaviorally equivalent and cannot be observed.)"""
    calls = []

    def boom():
        calls.append(1)
        raise _Err("HTTP 503 Service Unavailable")

    with pytest.raises(_Err):
        retry(boom, max_attempts=1, base_delay=0.0)
    assert len(calls) == 1
