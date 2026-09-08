"""A run of blank lines must not make the tell catalogue quadratic.

`score_tells("\\n" * 100_000)` did not finish. Six patterns anchored a MULTILINE `^` and then
matched `\\s*`, and `\\s` matches `\\n`: the anchor fires after EVERY newline, the quantifier eats
the whole remaining run, then backtracks one character at a time when the rest of the pattern
fails. O(N^2) on a document that is nothing but newlines.

`tests/test_scale_ceilings.py::test_all_newlines_score_tells` was already asserting the outcome and
had been hanging the whole suite rather than failing it. It went unnoticed because CI's lite job
aborted during collection and never ran a test at all.

Two tests here, because either alone is weak. The timing one proves the current tree is fixed but
says nothing about why; the structural one states the invariant, so a new pattern written the old
way fails on the rule rather than on a stopwatch.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
import time

import untell
from untell.scripts.tells import score_tells

# The shape that is safe is `[^\\S\\n]*` — horizontal whitespace, which cannot consume the newline
# run. The unsafe shape is a `\\s` quantifier reached shortly after a line anchor, where "shortly"
# has to tolerate the alternation the anchor usually sits inside:
#
#     (?:^|(?<=[.!?]\\s))\\s*(Moreover|...)      the anchor and the quantifier are 16 chars apart
#     (?m)^\\s*\\+\\s+\\w                          adjacent
#
# A single regex for that got the second and missed the FIRST, because a `[^)]*` hop cannot cross
# the `)` inside the lookbehind. Written as a scan instead, which is easier to read and to be right
# about. It is a lint heuristic, so a false positive costs one `[^\\S\\n]` and nothing else.
_ANCHOR = re.compile(r"(?<!\\)\^|\(\?<=\\n\)")
_CROSSES_NEWLINE = re.compile(r"\\s[*+]")


def _unsafe_span(pattern: str) -> str | None:
    r"""The first `\s`-quantifier REACHABLE from a line anchor with nothing mandatory between.

    Reachability is the whole point, and a proximity window got it wrong in both directions. It
    missed `(?:^|(?<=[.!?]\s))\s*` (the anchor and the quantifier are 16 characters and a nested
    `)` apart) and it flagged `(?m)^#{1,6}\s+(.+)$`, which is LINEAR: `#` has to match before the
    quantifier is ever reached, so a run of newlines fails at once. MEASURED, 100k newlines:
    0.0013s.

    So only two shapes count, and they are the two that occurred:

        (?m)^\s*\+\s+\w                      the quantifier directly follows the anchor
        (?:^|(?<=[.!?]\s))\s*(Moreover|...)  the anchor is one branch of a group, and the
                                             quantifier follows that group's closing paren
    """
    for anchor in _ANCHOR.finditer(pattern):
        hit = _CROSSES_NEWLINE.match(pattern, anchor.end())
        if hit:
            return pattern[anchor.start() : hit.end()]
        if pattern[anchor.end() : anchor.end() + 1] != "|":
            continue  # something else must match first; the quantifier is gated
        # Walk to the closing paren of the group this branch sits in. Escapes and character
        # classes are skipped, or the `)` in `[.!?]`-style classes would throw the depth off.
        depth, j, in_class = 1, anchor.end(), False
        while j < len(pattern) and depth:
            c = pattern[j]
            if c == "\\":
                j += 2
                continue
            if in_class:
                in_class = c != "]"
            elif c == "[":
                in_class = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            j += 1
        hit = _CROSSES_NEWLINE.match(pattern, j)
        if hit:
            return pattern[anchor.start() : hit.end()]
    return None


def _module_level_patterns():
    """Every compiled regex reachable as a module attribute under untell/."""
    for mod in pkgutil.walk_packages(untell.__path__, "untell."):
        try:
            module = importlib.import_module(mod.name)
        except Exception:  # optional-extra modules; their absence is covered elsewhere
            continue
        for name in dir(module):
            try:
                value = getattr(module, name)
            except Exception:
                continue
            if isinstance(value, re.Pattern):
                yield mod.name, name, value


def test_a_hundred_thousand_newlines_is_scored_promptly():
    """The known positive. Before the fix this did not return; 0.2s after.

    The bar is deliberately loose -- this is separating "finishes" from "does not finish", not
    benchmarking, so it must not fail on a loaded machine.
    """
    start = time.monotonic()
    result = score_tells("\n" * 100_000)
    elapsed = time.monotonic() - start
    assert result["tells"] == 0, "there is no prose here, so there are no tells"
    assert elapsed < 20.0, (
        f"score_tells took {elapsed:.1f}s on 100k newlines — a newline-crossing `\\s*` after a "
        f"MULTILINE `^` has probably come back; see _TRANSITION_OPENER_RE in scripts/tells.py"
    )


def test_no_multiline_pattern_lets_a_quantifier_cross_the_newline_run():
    """The invariant, stated once so the next pattern written this way fails here."""
    offenders = [
        f"{mod}.{name}: {pattern.pattern[:100]!r}"
        for mod, name, pattern in _module_level_patterns()
        if pattern.flags & re.MULTILINE and _unsafe_span(pattern.pattern)
    ]
    assert not offenders, (
        "a MULTILINE pattern quantifies `\\s` straight after a line anchor, which is quadratic on "
        "a run of blank lines. Use `[^\\S\\n]` (horizontal whitespace) instead:\n  "
        + "\n  ".join(offenders)
    )


def test_the_invariant_check_can_actually_fail():
    """The guard this repository's history says to write.

    A sweep that matches nothing looks exactly like a sweep that found nothing wrong. This asserts
    the detector fires on the real defect and stays quiet on the real fix.
    """
    assert _unsafe_span(r"(?:^|(?<=[.!?]\s))\s*(Moreover|Furthermore)\b")
    assert _unsafe_span(r"(?m)^\s*\+\s+\w")
    assert _unsafe_span(r"(?:^|(?<=[.!?]\s)|(?<=\n))\s*(Certainly!|Absolutely!)")
    assert not _unsafe_span(r"(?m)^[^\S\n]*\+[^\S\n]+\w")
    assert not _unsafe_span(r"(?:^|(?<=[.!?]\s))[^\S\n]*(Moreover|Furthermore)\b")
    # an escaped caret is a literal, not an anchor
    assert not _unsafe_span(r"a\^b\s*c")
    # `#` must match before the quantifier is reached, so a newline run fails immediately
    assert not _unsafe_span(r"(?m)^#{1,6}\s+(.+)$")
