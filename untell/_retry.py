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
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})
_RETRYABLE_ERRS = frozenset({
    "ConnectionError", "Timeout", "RateLimitError", "InternalServerError",
    "ServiceUnavailableError", "APITimeoutError", "APIConnectionError",
})


def _is_retryable(exc: Exception) -> bool:
    """Heuristic: is this a transient failure worth retrying?"""
    name = type(exc).__name__
    if name in _RETRYABLE_ERRS:
        return True
    msg = str(exc).lower()
    for keyword in ("rate limit", "too many requests", "try again", "temporarily",
                    "503", "502", "504", "429", "service unavailable", "timeout",
                    "connection reset", "connection refused", "broken pipe"):
        if keyword in msg:
            return True
    return False


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
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay) + random.random()
            time.sleep(delay)
    # Unreachable unless max_attempts == 0; satisfy type checker.
    raise RuntimeError("retry exhausted") from last_exc
