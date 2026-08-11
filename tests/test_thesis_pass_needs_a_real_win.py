"""The benchmark's headline claim could pass on a run where nothing happened.

`thesis_pass` compared `full_loop["bypass_rate"] >= single_pass["bypass_rate"]`. On real AI text
both are routinely 0%, so `>=` held trivially and the claim came back proven. MEASURED on 8 HC3
answers: single_pass 0%, full_loop 0%, `thesis_pass` True — while single_pass had actually scored
WORSE than doing nothing (0.6354 against noop's 0.6217).

The claim now needs a strict win somewhere, and `thesis_basis` says which comparison answered.
"""

from __future__ import annotations

from types import SimpleNamespace

from eval.report import summarize

THRESHOLD = 0.30


def _strategy(post_max: float, bypassed: int, n: int = 4, similarity: float = 0.99):
    """`bypassed` samples land under the threshold; the rest sit at `post_max`."""
    return [
        SimpleNamespace(
            pre={"detectors": {"d": 0.9}, "max": 0.9},
            post={
                "detectors": {"d": 0.10 if i < bypassed else post_max},
                "max": 0.10 if i < bypassed else post_max,
                "scored": True,
            },
            similarity=similarity,
            iterations=1,
        )
        for i in range(n)
    ]


def _run(sp, fl):
    return summarize({"single_pass": sp, "full_loop": fl}, THRESHOLD)


def test_two_zero_bypass_rates_do_not_prove_the_thesis():
    """The measured case. Neither strategy cleared anything, so bypass carries no information."""
    s = _run(_strategy(0.64, 0), _strategy(0.64, 0))
    assert s["thesis_pass"] is False
    assert "bypass tied" in s["thesis_basis"]


def test_a_tie_on_bypass_falls_through_to_the_unthresholded_score():
    s = _run(_strategy(0.64, 0), _strategy(0.60, 0))
    assert s["thesis_pass"] is True
    assert s["thesis_basis"] == "mean_post_max (bypass tied)"


def test_a_tie_on_bypass_with_a_worse_score_fails():
    s = _run(_strategy(0.60, 0), _strategy(0.64, 0))
    assert s["thesis_pass"] is False


def test_bypass_rate_decides_when_it_separates_them():
    s = _run(_strategy(0.64, 0), _strategy(0.64, 2))
    assert s["thesis_pass"] is True
    assert s["thesis_basis"] == "bypass_rate"


def test_the_loop_losing_on_bypass_fails_even_with_a_better_mean():
    """Bypass is the metric the thesis is stated in; a better mean must not rescue a worse rate.

    `post_max` stays above THRESHOLD here on purpose. The first version of this used 0.10, which
    is *under* the threshold, so every full_loop sample bypassed and the fixture handed the loop a
    100% rate — the test asserted a loss while constructing a win.
    """
    single_pass = _strategy(0.64, 2)          # 50% bypass, mean max 0.37
    full_loop = _strategy(0.31, 0)            # 0% bypass, mean max 0.31 — better mean, worse rate
    s = _run(single_pass, full_loop)
    assert s["strategies"]["full_loop"]["bypass_rate"] == 0.0, "premise: the loop cleared nothing"
    assert s["strategies"]["full_loop"]["mean_post_max"] < s["strategies"]["single_pass"]["mean_post_max"]
    assert s["thesis_pass"] is False
    assert s["thesis_basis"] == "bypass_rate"


def test_a_similarity_collapse_still_fails_the_thesis():
    s = _run(_strategy(0.64, 0, similarity=0.99), _strategy(0.40, 0, similarity=0.50))
    assert s["thesis_pass"] is False


def test_incomparable_denominators_still_block_the_claim():
    """The guard that was already here: unscored samples make the two rates non-comparable."""
    fl = _strategy(0.60, 0)
    fl[0].post["scored"] = False
    s = _run(_strategy(0.64, 0), fl)
    assert s["thesis_pass"] is False
    assert "not comparable" in s["thesis_undecided"]
