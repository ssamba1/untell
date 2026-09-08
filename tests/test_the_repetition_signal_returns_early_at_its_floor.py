"""`_repetition_signal`'s floor, which survived the boundary sweep.

    if ttr >= _TTR_FLOOR:
        return 0.0
    return clamp01((_TTR_FLOOR - ttr) / (_TTR_FLOOR - _TTR_SATURATION))

Round 135 filed this as an EQUIVALENT mutant and that was WRONG. The reasoning was that at
`ttr == _TTR_FLOOR` the fall-through evaluates `(FLOOR - FLOOR) / (FLOOR - SATURATION)`, which is
exactly 0.0 — the same value the early return gives. The value is the same; the WORK is not. Under
`>` a type-token ratio sitting exactly on the floor stops taking the early exit and runs the
division and the clamp instead.

Both this and `api_server.py:557` were called equivalent for the same bad reason: comparing what the
two operators RETURN and never asking what they DO. An equivalence argument has to cover the side
effects or it is not an equivalence argument.
"""

from __future__ import annotations

import pytest

from untell.detectors import perplexity_burstiness as pb
from untell.detectors.perplexity_burstiness import _TTR_FLOOR, _TTR_SATURATION


@pytest.fixture
def clamp_spy(monkeypatch):
    """Counts `clamp01` calls, which only the fall-through path makes."""
    calls: list[float] = []
    real = pb.clamp01

    def counting(value):
        calls.append(value)
        return real(value)

    monkeypatch.setattr(pb, "clamp01", counting)
    return calls


def _text_with_ttr(unique: int, total: int) -> str:
    """`total` words drawn from `unique` distinct ones, so the type-token ratio is exact.

    At least 40 words, or `_repetition_signal` returns 0.0 from its own short-text guard before
    reaching the comparison under test.
    """
    # Letters only: `_WORD` is `[A-Za-z']+`, so a numbered stem like `alpha0` tokenises to
    # `alpha` and every "distinct" word collapses to one — the ratio then lands nowhere near the
    # floor and the fixture silently tests the wrong branch.
    stems = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india",
             "juliet", "kilo", "lima", "mike", "november", "oscar", "papa"]
    assert unique <= len(stems)
    vocab = stems[:unique]
    words = [vocab[i % unique] for i in range(total)]
    assert len(set(words)) == unique and len(words) == total
    return " ".join(words)


def test_a_ratio_exactly_on_the_floor_takes_the_early_exit(clamp_spy):
    """40 words over 10 distinct is a ratio of exactly 0.25, the floor.

    The signal is 0.0 either way. What the early exit buys is not computing it, and the guard is
    what says "at or above the floor there is nothing to measure" rather than arriving at zero the
    long way round.
    """
    text = _text_with_ttr(unique=10, total=40)
    assert 10 / 40 == _TTR_FLOOR, "the fixture must sit ON the floor"

    assert pb._repetition_signal(text) == 0.0
    assert clamp_spy == [], (
        "a ratio exactly at the floor must return early, not fall through to the division")


def test_a_ratio_below_the_floor_falls_through_and_clamps(clamp_spy):
    """The neighbour: below the floor the signal is computed, so the assertion above is not just
    observing a function that never clamps."""
    text = _text_with_ttr(unique=8, total=40)  # 0.20, below the floor
    assert 8 / 40 < _TTR_FLOOR

    signal = pb._repetition_signal(text)
    assert clamp_spy, "below the floor the fall-through must run"
    assert signal > 0.0


def test_forty_words_is_exactly_the_short_text_guard_and_is_measured(clamp_spy):
    """The fixtures above are 40 words, which sits ON a second boundary: `if len(words) < 40`.

    That was luck, not design — the sweep reported this line newly killed and it was not in the
    prediction. Pinning it deliberately: 40 words is long enough to measure, 39 is not, and the
    guard says so rather than guessing from a ratio it does not trust.
    """
    assert pb._repetition_signal(_text_with_ttr(unique=8, total=40)) > 0.0
    assert clamp_spy, "40 words must reach the ratio; the guard admits it"

    clamp_spy.clear()
    assert pb._repetition_signal(_text_with_ttr(unique=8, total=39)) == 0.0
    assert clamp_spy == [], (
        "39 words is under the guard: too short for the ratio to be stable, so it says nothing "
        "rather than computing a signal it cannot support")


def test_the_floor_and_saturation_still_bracket_the_ramp():
    """Guard on both cases: a zero or inverted denominator would change what either one proves."""
    assert _TTR_SATURATION < _TTR_FLOOR
