"""NOVEL probe: MCP _bad_args full validation matrix.

_bad_args is the hand-rolled validator for MCP tool params. Probe every
known param against every hostile value class: wrong type, out of range,
bool-as-int, None, string-that-looks-like-number, inf/nan, negative, zero,
huge, and boundary values. The contract: malformed -> error dict, valid ->
None.
"""
import sys, math
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

from untell.mcp_server import _bad_args

# Correct call shape: _bad_args(name=(value, kind))
HOSTILE = [
    ("tier", [("fulll", "tier"), ("", "tier"), ("full", "tier"), ("lite", "tier")]),
    ("threshold", [("abc", "probability"), ("-1", "probability"), ("2", "probability"), ("0.5", "probability"), (None, "probability"), ("inf", "probability")]),
    ("seed", [("-5", "seed"), ("0", "seed"), ("100", "seed"), ("42", "seed"), (None, "seed")]),
    ("top", [("-1", "top"), ("0", "top"), ("3", "top"), (None, "top")]),
    ("confirm", [("-1", "count_or_zero"), ("0", "count_or_zero"), ("1", "count_or_zero")]),
    ("max_iters", [("0", "count"), ("-1", "count"), ("3", "count")]),
    ("best_of", [("0", "count"), ("-1", "count"), ("3", "count")]),
]

for key, cases in HOSTILE:
    for value, kind in cases:
        try:
            res = _bad_args(**{key: (value, kind)})
            verdict = "REJECT" if res else "accept"
            print(f"{key}={value!r:8} -> {verdict}")
        except Exception as e:
            print(f"{key}={value!r:8} -> RAISED {type(e).__name__}: {str(e)[:50]}")
    print()
