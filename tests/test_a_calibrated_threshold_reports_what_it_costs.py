"""A threshold that flags nothing has a perfect false-positive rate.

Roadmap item 18. `flagged` compares every document against ONE bar, 0.45, which assumes the score
distribution of human writing does not depend on length. It does: this repo measures **28.69%** of
60-100 word pre-ChatGPT abstracts flagged against **12.77%** above 200 — human text by construction,
so both are false-positive rates. A student handing in a short answer and a student handing in an
essay are judged by different standards while the tool reports one.

`eval/calibrated_thresholds.py` fixes the bar per length band by split conformal prediction, and
MEASURED on 500 pre-ChatGPT abstracts, lite:

    band       n   fixed bar  calib bar   FPR fixed  FPR calib   TPR fixed  TPR calib
    50-100    55      0.4500     0.6377       29.1%       3.6%        9.3%       2.3%
    100-200  418      0.4500     0.5383       15.8%       4.8%        9.1%       0.0%
    200+      27      0.4500     0.4696        3.7%       3.7%        0.0%       0.0%

The false-positive column is the improvement and the true-positive column is why it is not a win.
**At this tier the detector's TPR is already 9% before calibration and 0-2% after** — calibrating
away the false positives removes what little detection existed. The result is not "better
thresholds", it is "this tier cannot support a verdict at any threshold", which is a stronger claim
and only visible because both columns are reported.

These tests exist to keep the pair together. A calibration module that reports FPR alone would show
a triumphant 29.1% -> 3.6% and be worse than useless.
"""

from __future__ import annotations

import math

from eval import calibrated_thresholds as C


def test_every_calibrated_band_reports_the_sensitivity_it_costs() -> None:
    """The pair, enforced. Any threshold can be raised until nothing is flagged."""
    human = [f"word{i % 40} " * 120 for i in range(120)]
    machine = [f"word{i % 5} " * 120 for i in range(20)]
    report = C.calibrate(human, machine, target_fpr=0.05)
    for band in report["bands"]:
        if band.get("note"):
            continue
        assert "fpr_at_calibrated" in band, band
        assert "tpr_at_calibrated" in band, (
            f"band {band['band']} reports a false-positive rate with no sensitivity beside it"
        )


def test_the_conformal_quantile_uses_the_finite_sample_correction() -> None:
    """`ceil((n+1)(1-a))` rather than the plain quantile. Without the +1 the bar is fitted to the
    points it is evaluated on and the promised rate is optimistic by roughly 1/n — half a point on a
    200-document band, three points on a 30-document one, and the small bands are where this tool's
    error is worst."""
    scores = [i / 100 for i in range(100)]           # 0.00 .. 0.99
    bar = C.conformal_quantile(scores, 0.05)
    # ceil(101 * 0.95) = 96 -> the 96th smallest, which is 0.95. A plain 95th percentile gives 0.94.
    assert bar == 0.95, bar
    assert sum(1 for s in scores if s >= bar) / len(scores) <= 0.05


def test_a_band_too_small_to_certify_the_rate_says_so() -> None:
    """With n=5 no threshold can promise 1% — `ceil(6 * 0.99) = 6 > 5`. Returning the maximum score
    would hand back a bar the data cannot support, which is the "a zero meaning could-not-measure"
    error this repo names most often."""
    assert math.isinf(C.conformal_quantile([0.1, 0.2, 0.3, 0.4, 0.5], 0.01))
    assert math.isfinite(C.conformal_quantile([0.1, 0.2, 0.3, 0.4, 0.5], 0.5))


def test_an_under_powered_band_is_flagged_rather_than_given_a_number() -> None:
    human = [f"w{i} " * 120 for i in range(4)]
    report = C.calibrate(human, [], target_fpr=0.01)
    scored = [b for b in report["bands"] if not b.get("note")]
    assert scored, "the fixture produced no scored band"
    for band in scored:
        if band["under_powered"]:
            assert band["calibrated_threshold"] is None, (
                "an under-powered band must not publish a threshold"
            )


def test_the_exchangeability_caveat_travels_with_the_numbers() -> None:
    """The guarantee holds for documents drawn like the calibration set, and that set is ACL
    abstracts. A threshold quoted without that is a threshold quoted for the wrong corpus."""
    report = C.calibrate([f"w{i} " * 120 for i in range(60)], [], target_fpr=0.1)
    caveat = report["exchangeability_caveat"]
    assert "academic abstracts" in caveat and "cannot check" in caveat
    assert report["calibration_corpus"].startswith("ACL")


def test_the_fixed_bar_is_read_from_the_shipped_scorer_not_repeated() -> None:
    """This module argues about a number; hard-coding a second copy of it would let the argument
    drift from the thing it is arguing about."""
    import inspect

    source = inspect.getsource(C.shipped_threshold)
    assert "verdict_threshold" in source, "the bar must come from the scorer's own output"
    assert 0.0 < C.shipped_threshold() <= 1.0
