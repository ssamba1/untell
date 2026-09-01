"""A pattern that scales quadratically is a correctness bug wearing a performance costume.

`tests/test_scale_ceilings.py::test_all_newlines_score_tells` says "100k bare newlines must not
crash". It does not crash. It takes about **thirty-nine minutes**, which is why it was the last thing
still running when the suite appeared to hang — and the test's own docstring gave no hint, because
"does not crash" was the whole contract.

Five tell patterns were the cause. Each was `^` under `re.MULTILINE` followed by `\\s*`: every one of
n newlines is a line start, `\\s*` consumes the rest of the run before failing the literal, and the
engine backtracks over it. O(n) work at O(n) positions. MEASURED on `_claimed_spans`: 0.99s at 2,000
newlines, 3.92s at 4,000, 15.6s at 8,000, 60.5s at 16,000 — the clean 4x-per-2x signature.

`untell/scripts/score.py` caps REST input at 50,000 characters, and the cap does not bound the cost:
50,000 newlines extrapolates to about **ten minutes of CPU for a single request**. The fix restricts
those patterns to horizontal whitespace, which cannot cross a newline, and anchors four other
whitespace runs to their first character so interior positions fail in O(1).

This file is the durable half. Micro-fixing six patterns is worth less than making the seventh
impossible to add unnoticed, so it walks every compiled pattern reachable from `untell/` and `eval/`
and times it on the two inputs that trigger this: a run of newlines and a run of spaces.
"""

from __future__ import annotations

import importlib
import pathlib
import re
import time

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent

# Small enough that the whole sweep is a second or two, large enough that quadratic growth is
# unmistakable: a quadratic pattern is 4x slower for 2x the input, a linear one is 2x.
SMALL, LARGE = 3_000, 6_000
# Generous. A quadratic pattern is 4x slower for 2x the input and a linear one is 2x, so the midpoint
# would be 3.0; this sits below it to leave room for a pattern that is quadratic only in part, and
# above the 2.0 a purely linear one reaches. The measured offenders ran 15.8x-16.3x for a 4x input.
MAX_GROWTH = 2.8
# Below this, timing noise dominates the ratio and the growth figure means nothing. A quadratic
# pattern at LARGE is far above it: the six found here ran 0.03s-5.5s at these sizes.
NOISE_FLOOR_SECONDS = 0.03


def _patterns() -> list[tuple[str, re.Pattern]]:
    """Every compiled pattern reachable as a module attribute, or inside one collection deep."""
    found: dict[int, tuple[str, re.Pattern]] = {}

    def visit(obj, where):
        if isinstance(obj, re.Pattern):
            found.setdefault(id(obj), (where, obj))
        elif isinstance(obj, (list, tuple, set, frozenset)):
            for item in obj:
                visit(item, where)
        elif isinstance(obj, dict):
            for item in obj.values():
                visit(item, where)

    for directory in ("untell", "eval"):
        for path in sorted((REPO / directory).rglob("*.py")):
            if path.name == "__init__.py":
                continue
            name = str(path.relative_to(REPO).with_suffix("")).replace("/", ".")
            try:
                module = importlib.import_module(name)
            except ImportError:
                continue  # optional heavy dependency absent; other tests cover that
            for attribute in dir(module):
                try:
                    visit(getattr(module, attribute), f"{name}.{attribute}")
                except Exception:  # a property that raises is not a pattern
                    continue
    return sorted(found.values(), key=lambda pair: pair[0])


PATTERNS = _patterns()


# Timing under a loaded machine is noisy in one direction only: a scheduler steal adds time, it never
# removes any. So the minimum of a few runs is the robust estimator, and a mean or a single sample is
# not. MEASURED the hard way: with one sample this file passed alone and failed beside other test
# files, and a check that fails on a correct machine gets disabled, which is worse than no check.
_REPEATS = 3


def _seconds(pattern: re.Pattern, text: str) -> float:
    best = float("inf")
    for _ in range(_REPEATS):
        start = time.perf_counter()
        list(pattern.finditer(text))
        best = min(best, time.perf_counter() - start)
    return best


@pytest.mark.parametrize("filler,label", [("\n", "newlines"), (" ", "spaces")])
def test_no_reachable_pattern_is_quadratic_on_a_whitespace_run(filler, label):
    offenders = []
    for where, pattern in PATTERNS:
        try:
            small = _seconds(pattern, filler * SMALL)
            large = _seconds(pattern, filler * LARGE)
        except Exception:
            continue  # a pattern that raises on this input is a different test's problem
        if large < NOISE_FLOOR_SECONDS:
            continue
        growth = large / small if small > 0 else float("inf")
        if growth > MAX_GROWTH:
            offenders.append(f"{where}: {small:.3f}s at {SMALL} {label} -> {large:.3f}s at "
                             f"{LARGE} ({growth:.1f}x for 2x input); pattern {pattern.pattern[:80]!r}")
    assert not offenders, (
        f"{len(offenders)} pattern(s) grow superlinearly on a run of {label}. A greedy run that the "
        f"engine can re-enter at every character costs O(n^2). Two fixes work: restrict to "
        f"horizontal whitespace (`[^\\S\\n]*`) where a newline should stop the match, or anchor the "
        f"run to its first character with a negative lookbehind (`(?<!\\s)\\s+`):\n"
        + "\n".join(offenders))


def test_the_sweep_actually_reaches_the_patterns():
    """Guards the guard: a collector that found nothing would pass both cases above forever."""
    assert len(PATTERNS) > 150, f"only {len(PATTERNS)} patterns collected"
    names = {where for where, _ in PATTERNS}
    # One from each module the round-sixty-three fix touched, so a refactor that hides them fails.
    assert any(n.endswith("_TRAILING_HORIZONTAL") for n in names)
    assert any(n.endswith("_SENTENCE_END_AFTER") for n in names)
    assert any(n.endswith("_CATEGORIES") or "tells" in n for n in names)


def test_the_threshold_would_catch_the_pattern_shape_that_caused_this():
    """The exact retired construct, timed here rather than trusted.

    `^` under MULTILINE plus `\\s*` is the shape that cost thirty-nine minutes. If `MAX_GROWTH` were
    ever loosened to the point of accepting it, this fails and says so.
    """
    quadratic = re.compile(r"(?:^|(?<=[.!?]\s))\s*(Moreover|Furthermore)\b", re.MULTILINE)
    small = _seconds(quadratic, "\n" * SMALL)
    large = _seconds(quadratic, "\n" * LARGE)
    assert large > NOISE_FLOOR_SECONDS, "the probe is too fast to measure; raise SMALL and LARGE"
    assert large / small > MAX_GROWTH, (
        f"the known-quadratic construct grew only {large / small:.1f}x, so MAX_GROWTH="
        f"{MAX_GROWTH} would no longer catch it")


def test_the_shipped_replacement_is_linear_on_the_same_input():
    """The other half of the previous test: the fix must actually be the fix."""
    linear = re.compile(r"(?:^|(?<=[.!?]\s))[^\S\n]*(Moreover|Furthermore)\b", re.MULTILINE)
    quadratic = re.compile(r"(?:^|(?<=[.!?]\s))\s*(Moreover|Furthermore)\b", re.MULTILINE)
    text = "\n" * LARGE
    assert _seconds(linear, text) * 10 < _seconds(quadratic, text)
    # And it still finds the tell, at every position the old one did.
    for sample in ("Moreover, yes.", "Done. Furthermore, yes.", "\n\n  Moreover, indented.",
                   "a.\nMoreover, after a newline."):
        assert linear.search(sample), sample
