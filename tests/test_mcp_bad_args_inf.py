"""The MCP argument guard must refuse every malformed payload, not crash on some of them.

`_bad_args` exists so an MCP client can send ANYTHING and get a refusal dict rather than a
traceback — its docstring says so. Fuzz-found: the numeric kinds convert with int()/float(),
and only TypeError/ValueError were caught, so `int(float('inf'))` raised OverflowError
uncaught. This is reachable from a real client: Python's json module parses `1e999` as
`inf`, so a JSON-RPC call with `{"max_iters": 1e999}` crashed the tool. Same for best_of,
confirm, top, seed and ceiling's n.
"""

from __future__ import annotations

import pytest

from untell.mcp_server import _bad_args


@pytest.mark.parametrize(
    "name,kind",
    [
        ("max_iters", "count"),
        ("best_of", "count"),
        ("n", "count"),
        ("confirm", "count_or_zero"),
        ("top", "top"),
        ("seed", "seed"),
    ],
)
def test_infinite_count_is_a_refusal_not_a_crash(name, kind):
    """int(float('inf')) raises OverflowError; the guard must answer an error dict instead."""
    result = _bad_args(**{name: (float("inf"), kind)})
    assert result is not None
    assert "error" in result
    assert "not a number" in result["error"]


@pytest.mark.parametrize(
    "name,kind",
    [
        ("max_iters", "count"),
        ("best_of", "count"),
        ("confirm", "count_or_zero"),
        ("top", "top"),
        ("seed", "seed"),
    ],
)
def test_negative_infinity_is_a_refusal_not_a_crash(name, kind):
    result = _bad_args(**{name: (float("-inf"), kind)})
    assert result is not None and "error" in result


def test_huge_float_count_is_a_refusal_not_a_crash():
    """A giant-but-finite float converts to a giant int, then the range check must refuse it."""
    result = _bad_args(max_iters=(1e300, "count"))
    assert result is not None and "error" in result


def test_infinite_probability_is_a_refusal_not_a_crash():
    """The probability branch already survives inf via the range check; pin it."""
    result = _bad_args(threshold=(float("inf"), "probability"))
    assert result is not None and "error" in result
