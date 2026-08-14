"""Killing test: _retry retries on exception CLASS name (line 103), not just message.

An exception whose type name is in _RETRYABLE_ERRS but whose message contains no
retry keyword must still be retried. Mutating `return True` to `return False`
makes it fall through to the message-keyword checks and give up.
"""
import pytest

from untell._retry import _is_retryable


class RateLimitError(Exception):
    """Name matches _RETRYABLE_ERRS; message has no retry keyword."""


def test_class_name_alone_is_retryable():
    exc = RateLimitError("the service refused the request")  # no retry keyword in msg
    assert _is_retryable(exc) is True


def test_http_status_code_in_message_is_retryable():
    """Already-covered path kept for completeness: 503 in the message."""
    exc = Exception("upstream returned HTTP 503")
    assert _is_retryable(exc) is True


def test_plain_exception_is_not_retryable():
    exc = Exception("just a regular failure with no signal")
    assert _is_retryable(exc) is False
