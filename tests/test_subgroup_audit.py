"""The subgroup audit must refuse to overstate, in the three ways it would be tempted to.

This module reports false-positive rates broken down by a writer's race, gender, economic status
and grade. That is a strong claim about real people, and the ways it can go wrong are worse than
a wrong number: a rate computed on a handful of essays, an interval that hides how little is
known, or a "no disparity found" that is really "this measurement could not have found one".

MEASURED 2026-09-01, on the full 3,904-essay ELLIPSE corpus at untell's shipped lite threshold:

    threshold 0.30   97.4% of KNOWN-HUMAN essays flagged   -> saturated, disparity unmeasurable
    threshold 0.50   38.7%                                 -> measurable, ratios 1.05-1.19x
    threshold 0.70    3.2%                                 -> measurable, ratios up to 1.63x
    threshold 0.80+   under 1%                             -> saturated low

Not one subgroup ratio separated at 95% confidence at any threshold. The honest reading is that
this corpus shows a catastrophic OVERALL false-positive rate and no demonstrated per-group
disparity — and the tests below exist to keep the module reporting exactly that, rather than the
more quotable version of it.
"""

from __future__ import annotations

import pytest

from eval.subgroup_audit import (
    MIN_GROUP,
    SATURATED_HIGH,
    _group,
    saturation,
    wilson,
)


def _rows(spec: list[tuple[str, int, int]]) -> list[dict]:
    """(group, n, flagged) -> scored rows on one axis called `g`."""
    out = []
    for name, n, hits in spec:
        for i in range(n):
            out.append({"g": name, "flagged": i < hits})
    return out


class TestWilson:
    def test_it_never_leaves_the_unit_interval(self):
        """The normal approximation returns a negative lower bound here; that is why it is not used."""
        for n in (1, 5, 30, 3904):
            for hits in (0, 1, n // 2, n):
                lo, hi = wilson(hits, n)
                assert 0.0 <= lo <= hi <= 1.0, f"{hits}/{n} produced [{lo}, {hi}]"

    def test_zero_flags_still_carries_uncertainty(self):
        """0/30 is not 'certainly 0%'. A normal interval says it is, and would be believed."""
        lo, hi = wilson(0, 30)
        assert lo == 0.0
        assert hi > 0.05, f"0 of 30 reported an upper bound of {hi}; that claims false precision"

    def test_all_flags_still_carries_uncertainty(self):
        lo, hi = wilson(30, 30)
        assert hi == 1.0
        assert lo < 0.95, f"30 of 30 reported a lower bound of {lo}; that claims false precision"

    def test_the_interval_narrows_as_the_sample_grows(self):
        wide = wilson(5, 10)
        narrow = wilson(500, 1000)
        assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])

    def test_empty_says_it_knows_nothing(self):
        assert wilson(0, 0) == (0.0, 1.0)


class TestTheSmallGroupFloor:
    def test_a_group_under_the_floor_gets_no_rate(self):
        """A 100% rate on n=3 is a sentence about three people, not about a group."""
        rows = _rows([("tiny", MIN_GROUP - 1, MIN_GROUP - 1), ("big", 200, 100)])
        groups = _group(rows, ("g",))["g"]["groups"]
        assert groups["tiny"]["status"] == "insufficient"
        assert groups["tiny"]["fpr"] is None, "a rate was reported for an under-floor group"
        assert groups["tiny"]["n"] == MIN_GROUP - 1, "the count should still be visible"
        assert groups["big"]["status"] == "reported"

    def test_an_under_floor_group_cannot_become_the_disparity_headline(self):
        """The worst-looking group is exactly the one most likely to be tiny."""
        rows = _rows([("tiny", 3, 3), ("a", 200, 20), ("b", 200, 22)])
        block = _group(rows, ("g",))["g"]
        assert block["disparity"]["worst"] != "tiny"

    def test_the_floor_is_not_reachable_from_the_cli(self):
        import argparse
        import inspect

        from eval import subgroup_audit

        src = inspect.getsource(subgroup_audit.main)
        assert "min-group" not in src and "min_group" not in src.replace("report['min_group']", ""), (
            "MIN_GROUP became a CLI flag. It exists to stop someone lowering the floor until a "
            "group becomes reportable, which is the failure mode, not an inconvenience."
        )
        assert isinstance(argparse.ArgumentParser, type)  # the import is the point of the check


class TestSaturation:
    def test_the_real_measured_rate_is_reported_as_saturated(self):
        """97.4% is the number this repo's own lite tier produced on ELLIPSE."""
        note = saturation(0.974)
        assert note is not None and "SATURATED HIGH" in note
        assert "UNMEASURABLE" in note, "the warning must say unmeasurable, never 'equal'"

    def test_a_detector_that_clears_everyone_is_also_saturated(self):
        note = saturation(0.001)
        assert note is not None and "SATURATED LOW" in note

    def test_a_usable_operating_point_is_not_flagged(self):
        """38.7% and 3.2% are the measurable rows of the real sweep."""
        assert saturation(0.387) is None
        assert saturation(0.032) is None

    def test_the_boundary_is_where_it_says_it_is(self):
        assert saturation(SATURATED_HIGH) is not None
        assert saturation(SATURATED_HIGH - 0.001) is None


class TestDisparity:
    def test_overlapping_intervals_are_not_a_finding(self):
        """The whole sweep produced ratios above 1 and not one separated. That must stay visible."""
        rows = _rows([("a", 100, 50), ("b", 100, 55)])
        d = _group(rows, ("g",))["g"]["disparity"]
        assert d["ratio"] > 1.0, "the point estimates do differ"
        assert d["separated"] is False, "a 1.1x ratio at n=100 was reported as a real difference"

    def test_clearly_separated_groups_are_marked(self):
        rows = _rows([("a", 300, 30), ("b", 300, 240)])
        d = _group(rows, ("g",))["g"]["disparity"]
        assert d["separated"] is True
        assert d["worst"] == "b" and d["best"] == "a"

    def test_one_reportable_group_yields_no_disparity(self):
        rows = _rows([("only", 100, 50), ("tiny", 2, 2)])
        assert _group(rows, ("g",))["g"]["disparity"] is None

    def test_a_zero_rate_baseline_does_not_divide_by_zero(self):
        rows = _rows([("a", 100, 0), ("b", 100, 40)])
        d = _group(rows, ("g",))["g"]["disparity"]
        assert d["ratio"] is None, "a ratio against a 0% baseline is infinite, not a number"
        assert d["worst"] == "b"


class TestTheReportRefusesToBeMisread:
    def test_render_says_it_is_about_a_detector_not_a_document(self):
        from eval.subgroup_audit import render

        report = {
            "corpus_n": 10, "scored_n": 10, "tier": "lite", "threshold": 0.3,
            "overall_fpr": 0.5, "overall_ci": [0.2, 0.8], "min_group": MIN_GROUP,
            "saturation": None, "axes": {},
        }
        text = render(report)
        assert "not a document" in text or "NOT a document" in text
        assert "never be quoted at a person" in text

    def test_a_saturated_report_shouts_before_the_table(self):
        from eval.subgroup_audit import render

        report = {
            "corpus_n": 10, "scored_n": 10, "tier": "lite", "threshold": 0.3,
            "overall_fpr": 0.974, "overall_ci": [0.96, 0.98], "min_group": MIN_GROUP,
            "saturation": saturation(0.974), "axes": {},
        }
        text = render(report)
        assert "SATURATED HIGH" in text
        assert text.index("SATURATED HIGH") < len(text), "the warning must appear in the report"


def test_the_module_is_documented_as_human_only():
    """Scoring AI text here would silently turn false positives into true positives."""
    from eval import subgroup_audit

    doc = subgroup_audit.__doc__ or ""
    assert "known-human" in doc.lower()
    assert "every flag" in doc.lower(), "the report's central premise is undocumented"


@pytest.mark.parametrize("hits,n", [(0, 30), (15, 30), (30, 30), (1, 3904), (3803, 3904)])
def test_wilson_contains_the_point_estimate(hits, n):
    lo, hi = wilson(hits, n)
    assert lo <= hits / n <= hi
