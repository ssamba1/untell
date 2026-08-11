"""A per-detector row must never mix a pre-mean and a post-mean over different samples.

`summarize` was already fixed so the aggregate P(AI) figures share one denominator. The
per-detector table one row down still filtered its two sides independently, which turns a
detector that ERRORS on the hard samples into a detector that BEATS them.
"""

from types import SimpleNamespace

from eval.report import _hardest_detector, _per_detector, render


def _result(pre_detectors, post_detectors, similarity=0.9, iterations=1):
    def _max(d):
        vals = [v for v in d.values() if isinstance(v, (int, float))]
        return max(vals) if vals else 0.0

    return SimpleNamespace(
        pre={"detectors": pre_detectors, "max": _max(pre_detectors)},
        post={"detectors": post_detectors, "max": _max(post_detectors), "scored": True},
        similarity=similarity,
        iterations=iterations,
    )


def test_a_detector_that_errors_on_hard_samples_does_not_look_like_a_bypass():
    # radar scores 0.95 on all four inputs, then errors on the three hard ones.
    results = [
        _result({"radar": 0.95}, {"radar": 0.10}),
        _result({"radar": 0.95}, {"radar": "__error: cuda oom"}),
        _result({"radar": 0.95}, {"radar": "__error: cuda oom"}),
        _result({"radar": 0.95}, {"radar": "__error: cuda oom"}),
    ]
    row = _per_detector(results, threshold=0.30)["radar"]

    # The one sample that produced both numbers is the only one that may count.
    assert row["n"] == 1.0, "row must report the paired denominator, not the sample count"
    assert row["pre"] == 0.95
    assert row["post"] == 0.10

    # The bug: pre averaged over 4 while post averaged over 1, so the row read as a clean win.
    paired_pre = [0.95]
    assert row["pre"] == sum(paired_pre) / len(paired_pre)


def test_a_detector_with_no_paired_sample_is_not_the_hardest_to_beat():
    # `mage` runs on everything; `radar` errors post on every sample, so it has no paired data.
    results = [
        _result({"mage": 0.9, "radar": 0.9}, {"mage": 0.8, "radar": "__error"}),
        _result({"mage": 0.9, "radar": 0.9}, {"mage": 0.8, "radar": "__error"}),
    ]
    per_detector = _per_detector(results, threshold=0.30)

    assert per_detector["radar"]["n"] == 0.0
    # `_mean([])` is 0.0 — the lowest beat rate there is — so radar used to win this outright.
    assert _hardest_detector(per_detector) == "mage"


def test_hardest_detector_is_none_when_nothing_paired():
    results = [_result({"radar": 0.9}, {"radar": "__error"})]
    assert _hardest_detector(_per_detector(results, threshold=0.30)) is None


def test_render_marks_a_short_denominator_instead_of_implying_the_full_one():
    results = [
        _result({"radar": 0.95}, {"radar": 0.10}),
        _result({"radar": 0.95}, {"radar": "__error"}),
    ]
    out = render({"full_loop": results}, threshold=0.30)
    assert "[n=1]" in out, "a beat rate over fewer samples must show its own denominator"


def test_render_does_not_print_a_zero_row_for_an_absent_detector():
    results = [_result({"radar": 0.9}, {"radar": "__error"})]
    out = render({"full_loop": results}, threshold=0.30)
    assert "0.00->0.00" not in out, "no paired data must render as '-', not as a perfect score"
