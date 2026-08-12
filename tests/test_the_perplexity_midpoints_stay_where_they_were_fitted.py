"""The refit midpoints are load-bearing and nothing asserted them.

`_NLL_MID`/`_SPREAD_MID` moved 3.036/0.625 -> 2.680/0.400, and the fit comment records held-out
FPR 37% -> 12% at unchanged TPR. Reverting both constants left the whole suite green: the numbers
that decide every GPT-2-path verdict were unpinned.

A corpus test would need GPT-2 and HC3. Instead `_full_score` is fed synthetic token surprisals
whose mean and per-sentence spread ARE the distribution points the fit comment names, so the
calibration curve is exercised through the real code path at known inputs.

MEASURED through that harness, at the six range endpoints from the fit comment:

    point               new 2.680/0.400   old 3.036/0.625
    human median              0.094             0.196
    human low tail            0.416             0.625
    human high tail           0.002             0.006
    ai median                 0.633             0.799
    ai high tail              0.357             0.550
    ai low tail               0.828             0.920

The refit lowered every score, not only the human ones — worth stating, because the comment
records "TPR unchanged at 100%" and that is true at the 0.30 cut while the AI-side MARGIN above
that cut shrank from 0.250 to 0.057 at the AI upper corner. The last test here exists to fail
loudly if a future refit spends the rest of it.
"""
from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy")

import untell.detectors.perplexity_burstiness as PB  # noqa: E402

TEXT = (
    "Alpha alpha alpha alpha. Beta beta beta beta. "
    "Gamma gamma gamma gamma. Delta delta delta delta."
)

# The fitted distribution, quoted from the comment above the constants:
#   mean surprisal   human 3.85 [3.09, 5.15]   ai 2.23 [1.85, 2.62]
#   sentence spread  human 0.78 [0.23, 1.74]   ai 0.48 [0.19, 0.89]
HUMAN_MEDIAN = (3.85, 0.78)
HUMAN_LOW_TAIL = (3.09, 0.23)   # the human corner closest to the AI class
AI_MEDIAN = (2.23, 0.48)
AI_HIGH_TAIL = (2.62, 0.89)     # the AI corner closest to the human class

OLD_MIDPOINTS = (3.036, 0.625)
LOOP_THRESHOLD = 0.30


def _fake_nll(mean_nll: float, spread: float):
    """Token surprisals with a known mean and a known per-sentence population spread.

    Every token in a sentence gets that sentence's value, so the per-sentence means are exactly
    the values chosen and their spread is exactly `spread`. Verified by
    `test_the_synthetic_surprisals_reproduce_the_requested_statistics` rather than assumed — a
    harness that quietly produced different inputs would make every number below meaningless.
    """
    pos, bounds = 0, []
    for sentence in PB._sentences(TEXT):
        start = TEXT.find(sentence, pos)
        bounds.append((start, start + len(sentence)))
        pos = start + len(sentence)

    alternating = [mean_nll - spread, mean_nll + spread] * len(bounds)
    nll: list[float] = []
    offsets: list[tuple[int, int]] = []
    for (start, end), value in zip(bounds, alternating):
        step = max(1, (end - start) // 5)
        for k in range(4):  # >= 3 tokens, which is what _full_score requires per sentence
            a = start + k * step
            b = min(a + step, end)
            nll.append(value)
            offsets.append((a, b if b > a else a + 1))
    return np.array(nll, dtype=float), offsets


def _score_at(mean_nll, spread, midpoints=None, monkeypatch=None):
    detector = PB.PerplexityBurstinessDetector()
    detector._token_nll = lambda _text: _fake_nll(mean_nll, spread)
    if midpoints is not None:
        monkeypatch.setattr(PB, "_NLL_MID", midpoints[0])
        monkeypatch.setattr(PB, "_SPREAD_MID", midpoints[1])
    return detector._full_score(TEXT)


def test_the_synthetic_surprisals_reproduce_the_requested_statistics():
    """Validate the harness against a known positive before trusting anything it measures."""
    for mean_nll, spread in (HUMAN_MEDIAN, AI_MEDIAN):
        nll, offsets = _fake_nll(mean_nll, spread)
        assert float(nll.mean()) == pytest.approx(mean_nll, abs=1e-9)

        per_sentence, pos = [], 0
        for sentence in PB._sentences(TEXT):
            start = TEXT.find(sentence, pos)
            end = start + len(sentence)
            pos = end
            vals = [float(v) for v, (a, b) in zip(nll, offsets) if a >= start and b <= end and b > a]
            assert len(vals) >= 3, "a sentence contributed too few tokens to be grouped"
            per_sentence.append(sum(vals) / len(vals))

        centre = sum(per_sentence) / len(per_sentence)
        got = math.sqrt(sum((x - centre) ** 2 for x in per_sentence) / len(per_sentence))
        assert got == pytest.approx(spread, abs=1e-9)


@pytest.mark.parametrize(
    "label,point,expected",
    [
        ("human median", HUMAN_MEDIAN, 0.094),
        ("human low tail", HUMAN_LOW_TAIL, 0.416),
        ("ai median", AI_MEDIAN, 0.633),
        ("ai high tail", AI_HIGH_TAIL, 0.357),
    ],
)
def test_the_calibration_curve_maps_the_fitted_range_where_it_was_measured(label, point, expected):
    assert _score_at(*point) == pytest.approx(expected, abs=0.01), (
        f"the {label} of the fitted distribution no longer maps where the refit put it; "
        f"_NLL_MID/_SPREAD_MID are {PB._NLL_MID}/{PB._SPREAD_MID}"
    )


@pytest.mark.parametrize("point", [HUMAN_MEDIAN, HUMAN_LOW_TAIL], ids=["median", "low_tail"])
def test_reverting_the_midpoints_raises_the_score_on_human_text(point, monkeypatch):
    """The revert this suite could not previously detect. FPR 37% -> 12% was bought here."""
    refit = _score_at(*point)
    reverted = _score_at(*point, midpoints=OLD_MIDPOINTS, monkeypatch=monkeypatch)
    assert reverted > refit + 0.05, (
        f"the old midpoints score human text at {reverted:.3f} against the refit's {refit:.3f}; "
        "if these are close, the constants under test are no longer the refit ones"
    )


def test_the_human_low_tail_is_the_corner_the_refit_did_not_fully_fix():
    """Honest about what was bought: 0.625 -> 0.416 still sits above the 0.30 loop threshold."""
    assert _score_at(*HUMAN_LOW_TAIL) > LOOP_THRESHOLD, (
        "the human corner nearest the AI class now clears the loop threshold — good news, but the "
        "fit comment's 12% held-out FPR says otherwise, so one of the two is stale"
    )


def test_ai_text_at_the_far_corner_still_clears_the_loop_threshold():
    """The margin the refit spent. 0.550 -> 0.357 against a 0.30 cut leaves 0.057.

    TPR held at 100% because this stayed above the line, not because it was unaffected. A further
    downward refit fails here first, which is the point — it is the cheapest possible warning that
    the AI side has run out of room.
    """
    score = _score_at(*AI_HIGH_TAIL)
    assert score > LOOP_THRESHOLD, (
        f"AI text at the top of the fitted AI range scores {score:.3f}, at or below the {LOOP_THRESHOLD} "
        "loop threshold — the detector no longer flags AI text inside its own fitted range"
    )
    assert score - LOOP_THRESHOLD < 0.15, (
        "margin is wider than measured; re-check the table in this module's docstring"
    )
