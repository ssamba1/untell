"""Exponential-backoff retry wrapper for flaky API calls.

Transient failures (rate limits, network blips, 5xx) are retried with
exponential backoff + jitter so they don't abort the rewrite loop.

Usage::

    from untell._retry import retry

    result = retry(api_call, args=(text,), kw={"model": "claude"}, max_attempts=3)

``max_attempts=1`` disables retry (useful for testing).
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

# A private stream. `random.random()` draws from the PROCESS-GLOBAL generator, so a retry — which
# fires on someone else's failure, at an unpredictable moment — would silently advance a caller's
# reproducible sequence. `structural_rewrite` already carries the same fix for the same reason.
_JITTER = random.Random()

# 408 Request Timeout and 529 Overloaded were absent. 529 is the one that matters here: it is
# Anthropic's capacity code, and this package ships an Anthropic rewriter — so the one provider
# whose overload signal we would see most often was the one not retried. Found by checking a
# realistic message (`anthropic.APIStatusError: 529 overloaded`) against the classifier rather than
# by reading the set, which looks complete until you ask it about a specific provider.
_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504, 529})
_RETRYABLE_ERRS = frozenset({
    "ConnectionError", "Timeout", "RateLimitError", "InternalServerError",
    "ServiceUnavailableError", "APITimeoutError", "APIConnectionError",
})


# Read the status codes out of the message and test them against `_RETRYABLE_HTTP`, rather than
# listing them again as strings. They WERE listed again, and the two copies had already drifted:
# the set says 500 is retryable, the string list contained "503", "502", "504", "429" and not
# "500", and `_RETRYABLE_HTTP` was referenced exactly once in the module — its own definition. So a
# provider raising a plain exception carrying "HTTP 500" was not retried while 502/503/504 were,
# and the set that documented the intent had no effect on anything.
#
# The code has to look like a STATUS, not merely be a three-digit number. A bare `\b([1-5]\d{2})\b`
# matched any of them anywhere in the message, so a permanent error was retried three times with
# backoff because its text happened to mention one. MEASURED against nine realistic non-retryable
# messages, four were retried:
#
#     invalid_request_error: max_tokens must be <= 500
#     context length 502 tokens exceeds the 500 token limit
#     ValueError: expected 429 items in the batch, got 12
#     invalid parameter: timeout must be a positive number      (the keyword below, not this regex)
#
# The first three are configuration mistakes that will fail identically on every attempt, and the
# last is a bug in our own call being masked by a retry. So the code must sit where providers put
# one: at the head of the message, or straight after http/status/code/error.
# `\w*` after the keyword so `HTTPError: 500` matches — there is no word boundary inside that token,
# and a first version of this missed it. The bracket alternative covers `(429) rate_limit_exceeded`,
# which providers also emit. Both were caught by checking the genuine retryables as carefully as the
# false positives: tightening a rule is exactly when the other direction breaks.
# The optional `api`/`http` prefix is for the SDK exception classes that actually appear here —
# `APIStatusError: 500`, `HTTPError: 500` — where the keyword has no word boundary before it.
_STATUS_RE = re.compile(
    r"(?:^|[(\[]|\b(?:api|http)?(?:https?|status|code|error)\w*[\s:=]*)([1-5]\d{2})\b",
    re.IGNORECASE,
)

# `timeout` on its own matched "timeout must be a positive number" — a parameter being named, not a
# request timing out. These are the shapes an actual timeout takes.
_TIMEOUT_PHRASES = ("timed out", "read timeout", "connection timeout", "request timeout",
                    "timeout exceeded", "timeout after")


# Builtins, matched by TYPE rather than by name. The name set below misses every subclass, and the
# subclasses are the ones actually raised: `ConnectionResetError`, `ConnectionAbortedError` and
# `ConnectionRefusedError` all inherit from `ConnectionError`, which IS in the name set, and none of
# them shares its name. MEASURED before this:
#
#     ConnectionError          retryable
#     ConnectionResetError     NOT retried
#     ConnectionAbortedError   NOT retried
#     ConnectionRefusedError   NOT retried
#     TimeoutError             NOT retried
#     BrokenPipeError          retried — but only because its default message says "broken pipe"
#
# So the classifier's most-cited signal was matching a base class nobody raises directly, and the
# real ones were reaching it through their message text or not at all. The name set stays for
# third-party SDK exceptions, which cannot be imported here without taking a dependency on them.
_RETRYABLE_TYPES: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError)


def _is_retryable(exc: Exception) -> bool:
    """Heuristic: is this a transient failure worth retrying?"""
    if isinstance(exc, _RETRYABLE_TYPES):
        return True
    name = type(exc).__name__
    if name in _RETRYABLE_ERRS:
        return True
    msg = str(exc).lower()
    if any(int(code) in _RETRYABLE_HTTP for code in _STATUS_RE.findall(msg)):
        return True
    for keyword in ("rate limit", "too many requests", "try again", "temporarily",
                    "service unavailable",
                    "connection reset", "connection refused", "broken pipe"):
        if keyword in msg:
            return True
    return any(phrase in msg for phrase in _TIMEOUT_PHRASES)


def retry(
    fn: Callable[..., T],
    args: tuple = (),
    kw: dict | None = None,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> T:
    """Call ``fn(*args, **kw)``, retrying up to ``max_attempts`` times on transient errors.

    Backoff: ``base_delay * 2^attempt + jitter(0, 1)``, capped at ``max_delay``.
    The last exception is re-raised if all attempts fail.
    """
    if max_attempts < 1:
        max_attempts = 1
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **(kw or {}))
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts or not _is_retryable(exc):
                raise
            # Cap AFTER the jitter, not before. Adding it afterwards put the real ceiling at
            # `max_delay + 1` (measured 30.784 against a documented 30.0), so the one number this
            # function promises a caller was the one number it did not honour.
            delay = min(base_delay * (2 ** (attempt - 1)) + _JITTER.random(), max_delay)
            time.sleep(delay)
    # Unreachable unless max_attempts == 0; satisfy type checker.
    raise RuntimeError("retry exhausted") from last_exc
