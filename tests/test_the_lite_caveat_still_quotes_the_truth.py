"""The most-shown message in this tool quotes two percentages, and nothing checked them.

The lite-tier caveat fires on **120 of 120** corpus texts (Result 182) — every single run on the
default install carries it. It says:

    "Re-measured on 100 HC3 pairs: 64% of HUMAN text scores above the 0.30 loop threshold, and
     30% is FLAGGED"

MEASURED at n=100, HC3 human halves, stdlib lite path: **64/100 and 30/100**, exactly. Both figures
land on the nose, which is why this file pins them rather than correcting them.

It is worth pinning because this session found the same class of defect twice in messages nobody was
checking. Result 205: `humanness` told users human prose sits near 0.70 burstiness, which 7 of 80
human documents reach. Result 207: the short-text bands overstated by 20 to 100 points on the only
path that could have produced them. Both were numbers in prose, both correct when written, both
unguarded — and a detector change is all it takes to make this one join them.

Asserted at the SAME n=100 the sentence quotes, with a five-point tolerance. A cheaper n=40 run was
tried first and gave 52.5% and 17.5% against the claimed 64% and 30% — a twelve-point swing from
sample size alone. The claim is about 100 pairs, so pinning it at 40 pins a different claim; the
tolerance covers detector jitter, not a change of denominator.

The path is pinned explicitly. The lite tier silently uses GPT-2 when torch is importable, the two
paths disagree by a factor of three on exactly this measurement, and Result 196 records a wrong
conclusion reached by not checking which one ran.
"""

from __future__ import annotations

import logging
import re

import pytest

from untell.scripts.score import score_text

TOLERANCE = 5  # percentage points
CLAIMED_ABOVE_THRESHOLD = 64
CLAIMED_FLAGGED = 30


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def human_texts() -> list[str]:
    pytest.importorskip("datasets")
    from eval.datasets import load_pairs

    pairs = load_pairs("hc3", n=100, min_words=60)
    texts = [h for h, _ in pairs][:100]
    if len(texts) < 80:
        pytest.skip("needs the HC3 pairs")
    return texts


@pytest.fixture(scope="module")
def rates(human_texts, stdlib_lite_env) -> tuple[float, float]:
    scored = [score_text(t, tier="lite", threshold=0.3) for t in human_texts]
    live = [s for s in scored if s.get("max") is not None]
    assert live, "nothing scored; the rates below would be meaningless"
    above = 100 * sum(1 for s in live if s["max"] >= 0.30) / len(live)
    flagged = 100 * sum(1 for s in live if s["flagged"]) / len(live)
    return above, flagged


@pytest.fixture(scope="module")
def stdlib_lite_env():
    """Pin the scoring path for the whole module. `conftest.stdlib_lite` is function-scoped and this
    fixture is module-scoped, so it cannot be reused directly."""
    import os

    from untell.scripts import score as score_mod

    def _clear() -> None:
        # The scorers are cached, so flipping the variable without clearing them serves results
        # from the other path. `conftest.stdlib_lite` does this for the same reason; the first
        # version of this fixture did not, and measured 52.5%/17.5% against a claimed 64%/30%.
        for name in ("score_text", "batch_score_texts"):
            fn = getattr(score_mod, name, None)
            if hasattr(fn, "cache_clear"):
                fn.cache_clear()

    previous = os.environ.get("UNTELL_LITE_NO_TORCH")
    os.environ["UNTELL_LITE_NO_TORCH"] = "1"
    _clear()
    yield
    if previous is None:
        os.environ.pop("UNTELL_LITE_NO_TORCH", None)
    else:
        os.environ["UNTELL_LITE_NO_TORCH"] = previous
    _clear()


def test_the_caveat_still_quotes_these_numbers(stdlib_lite_env) -> None:
    """The premise. If the sentence is reworded, the assertions below are checking a claim the tool
    no longer makes, and should be updated with it rather than left passing."""
    text = (
        "Salt lowers the freezing point of water, which is why councils spread it on roads in "
        "winter. It works down to about minus nine degrees, below which other chemicals are needed "
        "instead, and the grit does a second job once the ice has gone soft near the kerb edge."
    )
    warning = score_text(text, tier="lite").get("warning") or ""
    assert f"{CLAIMED_ABOVE_THRESHOLD}% of HUMAN text" in warning, warning[:160]
    assert f"{CLAIMED_FLAGGED}% is FLAGGED" in warning, warning[:160]


@pytest.mark.slow
def test_the_above_threshold_rate_matches_the_claim(rates) -> None:
    above, _ = rates
    assert abs(above - CLAIMED_ABOVE_THRESHOLD) <= TOLERANCE, above


@pytest.mark.slow
def test_the_flagged_rate_matches_the_claim(rates) -> None:
    """This is the number that decides whether a human is told their own writing reads as AI, so it
    is the one worth catching early if it moves."""
    _, flagged = rates
    assert abs(flagged - CLAIMED_FLAGGED) <= TOLERANCE, flagged


@pytest.mark.slow
def test_the_two_rates_are_not_the_same_number(rates) -> None:
    """Guards the guard. The whole point of the sentence is that `flagged` uses the 0.45 verdict
    threshold and the loop uses 0.30, so the two answer different questions — if they converged, the
    caveat would be explaining a distinction that no longer exists."""
    above, flagged = rates
    assert above - flagged > 10, (above, flagged)


def test_every_number_in_the_caveat_is_covered(stdlib_lite_env) -> None:
    """A caveat can gain a figure, and this file would keep passing while the new one went
    unchecked. The lite sentence quotes six: 100 pairs, 64%, 0.30, 30%, 0.45, and the 10%/70% clear
    rates. Any change to that inventory should fail here and be decided deliberately.
    """
    text = (
        "Salt lowers the freezing point of water, which is why councils spread it on roads in "
        "winter. It works down to about minus nine degrees, below which other chemicals are needed "
        "instead, and the grit does a second job once the ice has gone soft near the kerb edge."
    )
    warning = score_text(text, tier="lite").get("warning") or ""
    start = warning.find("lite tier on the stdlib path")
    assert start >= 0, "the lite caveat is not in this warning"
    sentence = warning[start:]
    # Read off the sentence rather than written from memory — the first version of this assertion
    # listed the figures I remembered it quoting and missed `1.000` and the two `n=30` denominators.
    expected = {"0.30", "0.45", "1.000", "10%", "100", "3", "30", "30%", "64%", "70%"}
    numbers = set(re.findall(r"\d+(?:\.\d+)?%?", sentence))
    assert numbers == expected, {"new": sorted(numbers - expected), "gone": sorted(expected - numbers)}
