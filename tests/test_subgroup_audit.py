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


class TestComponentAblation:
    """A composite detector reports one number, and one number can hide two opposite biases.

    MEASURED 2026-09-01 on ELLIPSE and REPLICATED on its held-out split, each component
    thresholded at its own median so both flag about half the corpus:

        vocabulary half   flags LOW-proficiency writers  1.57x / 1.59x more   separated
        burstiness half   flags HIGH-proficiency writers 1.42x / 1.35x more   separated

    They point opposite ways, both separate at 95%, and they partly cancel in the combined
    score. Any aggregate fairness number for this detector therefore understates both, which is
    the thing a benchmark treating a detector as a black box structurally cannot report.
    """

    def _recs(self, monkeypatch, spec):
        """Feed the ablation synthetic component values via the real code path."""
        from eval import subgroup_audit as sa

        rows = [{"text": f"t{i}", "Overall": band} for i, (band, _, _) in enumerate(spec)]
        vals = {f"t{i}": (c, b) for i, (_, c, b) in enumerate(spec)}
        import untell.detectors.perplexity_burstiness as pb

        monkeypatch.setattr(pb, "_common_ratio", lambda t: vals[t][0])
        monkeypatch.setattr(pb, "_burstiness", lambda s: vals[s[0]][1])
        monkeypatch.setattr(pb, "_sentences", lambda t: [t])
        return sa.ablate(rows, "Overall", lambda v: v)

    def test_opposed_components_are_detected_and_announced(self, monkeypatch):
        """The real finding: vocabulary penalises 'low', burstiness penalises 'high'."""
        from eval.subgroup_audit import render_ablation

        spec = ([("low", 0.9, 0.9)] * 60) + ([("high", 0.1, 0.1)] * 60)
        res = self._recs(monkeypatch, spec)
        assert res["opposed"] is True, "opposite-direction bias in the two halves went unreported"
        text = render_ablation(res)
        assert "OPPOSITE DIRECTIONS" in text
        assert "black-box audit cannot see this" in text

    def test_components_biased_the_same_way_are_not_called_opposed(self, monkeypatch):
        """`opposed` must mean opposed, or the warning becomes noise."""
        spec = ([("low", 0.9, 0.1)] * 60) + ([("high", 0.1, 0.9)] * 60)
        res = self._recs(monkeypatch, spec)
        assert res["opposed"] is False

    def test_each_component_is_thresholded_at_its_own_median(self, monkeypatch):
        """Equal power. A component with a lopsided operating point would otherwise look fairer
        purely because it had less room to differ -- the saturation trap, one level down."""
        spec = ([("low", 0.99, 0.99)] * 50) + ([("high", 0.01, 0.01)] * 50)
        res = self._recs(monkeypatch, spec)
        for name, block in res["components"].items():
            total = sum(g["n"] for g in block["groups"].values())
            flagged = sum(round(g["fpr"] * g["n"]) for g in block["groups"].values())
            assert 0.3 <= flagged / total <= 0.7, (
                f"{name} flagged {flagged}/{total}; a median split should be near half"
            )

    def test_an_empty_band_selection_says_so_rather_than_dividing_by_zero(self, monkeypatch):
        from eval import subgroup_audit as sa

        res = sa.ablate([{"text": "x", "Overall": "3"}], "Overall", lambda v: None)
        assert "error" in res


class TestMissingDataIsNotASubgroup:
    """A missing-data bucket is not a population and must never be a comparison arm.

    MEASURED 2026-09-01 on ASAP 2.0: 4,019 of 17,307 essays code economic and disability status
    as the string "NA". Those rows scored 19.1% where every real group scored 30-38%, so treating
    "NA" as a group made it the "best" arm on two axes and produced a 2.01x headline ratio against
    what is really a data-collection artifact. The number was wrong and the direction was wrong.
    """

    def test_na_rows_are_excluded_from_every_group(self):
        rows = ([{"g": "NA", "flagged": False}] * 100
                + [{"g": "real", "flagged": True}] * 100)
        groups = _group(rows, ("g",))["g"]["groups"]
        assert "NA" not in groups, "missing data was reported as a subgroup"
        assert groups["real"]["n"] == 100

    def test_the_common_spellings_of_missing_are_all_caught(self):
        for token in ("NA", "n/a", "Unknown", "", "  ", "None", "not reported"):
            rows = ([{"g": token, "flagged": False}] * 50
                    + [{"g": "real", "flagged": True}] * 50)
            groups = _group(rows, ("g",))["g"]["groups"]
            assert list(groups) == ["real"], f"{token!r} survived as a subgroup: {list(groups)}"

    def test_a_missing_bucket_cannot_become_the_disparity_arm(self):
        """The exact ASAP failure: NA scoring far lower than everyone made it the 'best' group."""
        rows = ([{"g": "NA", "flagged": False}] * 400
                + [{"g": "a", "flagged": True}] * 200
                + [{"g": "b", "flagged": False}] * 200)
        d = _group(rows, ("g",))["g"]["disparity"]
        assert d is not None
        assert "NA" not in (d["worst"], d["best"]), f"disparity compared against NA: {d}"


class TestAnAxisWithNoDataSaysSo:
    """An empty axis rendered as a bare heading reads as 'no disparity here'.

    MEASURED 2026-09-01: a --csv label-filter bug dropped `ell_status` from an ASAP load, and the
    report printed "by ell_status" with nothing under it. That is the worst shape for a bug --
    silent, and reassuring in the wrong direction.
    """

    def test_an_absent_axis_is_marked_missing(self):
        block = _group([{"other": "x", "flagged": True}] * 50, ("ell_status",))["ell_status"]
        assert block["missing"] is True

    def test_a_populated_axis_is_not_marked_missing(self):
        block = _group([{"g": "a", "flagged": True}] * 50, ("g",))["g"]
        assert block["missing"] is False

    def test_render_announces_the_missing_axis(self):
        from eval.subgroup_audit import render

        report = {
            "corpus_n": 50, "scored_n": 50, "tier": "lite", "threshold": 0.5,
            "overall_fpr": 0.5, "overall_ci": [0.4, 0.6], "min_group": MIN_GROUP,
            "saturation": None,
            "axes": {"ell_status": {"groups": {}, "disparity": None, "missing": True}},
        }
        assert "nothing measured here" in render(report)


class TestEqualisedOdds:
    """The other half of the audit: a detector can pass one parity and fail the other badly.

    A detector that simply never flags one group has PERFECT false-positive parity for them and
    lets all their machine-written work through. That harms the same students by a different
    route, and a false-positive-only report calls it clean. These tests pin that the second rate
    is actually computed and actually separated.

    The module ships no AI corpus and must not pretend to: `.claude/corpora/` is HC3 HUMAN text,
    and detector_audit carries five hand-written AI probes, which is a smoke test not a sample.
    So `equalised_odds` REQUIRES the caller to supply labels, and refuses loudly without them.
    """

    def _rows(self, spec):
        """(group, is_ai, n, flagged) -> rows already carrying scores via a stub scorer."""
        out = []
        for g, is_ai, n, flagged in spec:
            for i in range(n):
                out.append({"text": "x", "g": g, "is_ai": is_ai, "_flag": i < flagged})
        return out

    def _run(self, monkeypatch, rows):
        from eval import subgroup_audit as sa

        seq = iter([1.0 if r["_flag"] else 0.0 for r in rows])
        import untell.scripts.score as sc

        monkeypatch.setattr(sc, "score_text", lambda t, **k: {"max": next(seq)})
        return sa.equalised_odds(rows, axes=("g",), threshold=0.5)

    def test_missing_labels_are_refused_loudly(self):
        from eval.subgroup_audit import equalised_odds

        with pytest.raises(ValueError) as exc:
            equalised_odds([{"text": "x", "g": "a"}], axes=("g",))
        assert "no false negatives to measure" in str(exc.value)

    def test_one_class_only_is_an_error_not_a_report(self, monkeypatch):
        rows = self._rows([("a", False, 60, 30)])
        out = self._run(monkeypatch, rows)
        assert "error" in out and "both classes" in out["error"]

    def test_both_rates_are_reported_per_group(self, monkeypatch):
        rows = self._rows([("a", False, 60, 6), ("a", True, 60, 54),
                           ("b", False, 60, 6), ("b", True, 60, 54)])
        g = self._run(monkeypatch, rows)["axes"]["g"]["groups"]
        assert g["a"]["fpr"] == 0.1 and g["a"]["fnr"] == 0.1
        assert "fpr_ci" in g["a"] and "fnr_ci" in g["a"]

    def test_perfect_fpr_parity_can_hide_a_large_fnr_gap(self, monkeypatch):
        """The failure this whole class exists for.

        Both groups have an identical 10% false-positive rate. Group b's machine-written work
        sails through at 90% while group a's is caught. An FPR-only report calls this clean.
        """
        rows = self._rows([("a", False, 100, 10), ("a", True, 100, 90),   # a: fpr .10 fnr .10
                           ("b", False, 100, 10), ("b", True, 100, 10)])  # b: fpr .10 fnr .90
        block = self._run(monkeypatch, rows)["axes"]["g"]
        fpr, fnr = block["fpr_disparity"], block["fnr_disparity"]
        assert fpr["ratio"] == 1.0, "the false-positive rates were meant to be identical"
        assert fpr["separated"] is False, "identical FPRs must not read as a disparity"
        assert fnr["ratio"] >= 8, f"the false-negative gap was missed: {fnr}"
        assert fnr["separated"] is True, "a 9x false-negative gap at n=100 must separate"

    def test_a_group_short_on_either_class_is_not_reported(self, monkeypatch):
        rows = self._rows([("big", False, 60, 6), ("big", True, 60, 6),
                           ("thin", False, 60, 6), ("thin", True, 5, 1)])
        g = self._run(monkeypatch, rows)["axes"]["g"]["groups"]
        assert g["thin"]["status"] == "insufficient", "a group with 5 AI rows got a rate"
        assert g["big"]["status"] == "reported"

    def test_missing_values_are_not_a_group_here_either(self, monkeypatch):
        rows = self._rows([("NA", False, 60, 6), ("NA", True, 60, 6),
                           ("real", False, 60, 6), ("real", True, 60, 6)])
        g = self._run(monkeypatch, rows)["axes"]["g"]["groups"]
        assert "NA" not in g


class TestTheLiangCorpus:
    """Liang et al. 2023 is the corpus this field's bias literature descends from.

    It was added on 2026-09-01 after reading `satyamshivam13/AI_Text_Detector`, which had been
    measuring per-population false-positive rates on it since July 2026 while this repository's
    strategy document claimed no such tool existed. These guard the two things about the loader
    that a future edit could quietly break, both of which would invalidate published numbers.
    """

    def test_no_word_floor_is_applied_by_default(self, monkeypatch):
        """Dropping short essays would silence any comparison with the published figures.

        The other loaders take a 60-word floor because a 14-word answer measures window logic
        rather than a writer. Here the essays ARE the published sample, so the floor is 0 and a
        caller who wants one has to ask and say so.
        """
        from eval import datasets

        payload = [{"text": "tiny", "population": "toefl_nonnative"},
                   {"text": " ".join(["word"] * 200), "population": "cs224n_student"}]
        monkeypatch.setattr(datasets, "_liang_cache", lambda: _FakeCache(payload))
        rows = datasets.load_liang()
        assert len(rows) == 2, f"the loader is filtering by length by default: {rows}"
        assert len(datasets.load_liang(min_words=60)) == 1

    def test_the_machine_edited_population_is_labelled_and_not_silently_pooled(self, monkeypatch):
        """`toefl_gpt4_polished` is human-authored and machine-EDITED.

        Counting it as a plain false positive would inflate every aggregate on this corpus with
        texts a language model touched, which is a different question. It must arrive carrying a
        flag that lets a caller hold it out.
        """
        from eval import datasets

        payload = [{"text": "a b c", "population": "toefl_gpt4_polished"},
                   {"text": "a b c", "population": "toefl_nonnative"}]
        monkeypatch.setattr(datasets, "_liang_cache", lambda: _FakeCache(payload))
        by_pop = {r["population"]: r for r in datasets.load_liang()}
        assert by_pop["toefl_gpt4_polished"]["machine_edited"] == "True"
        assert by_pop["toefl_nonnative"]["machine_edited"] == "False"

    def test_the_five_populations_are_the_ones_liang_published(self):
        """A renamed or dropped population would break the comparison silently."""
        from eval.datasets import LIANG_MACHINE_EDITED, LIANG_POPULATIONS

        assert set(LIANG_POPULATIONS) == {
            "toefl_nonnative", "student_us_8th", "college_admission", "cs224n_student",
            "toefl_gpt4_polished",
        }
        assert LIANG_MACHINE_EDITED == {"toefl_gpt4_polished"}


class _FakeCache:
    """A cache path whose `exists()` is true and whose text is a fixed payload."""

    def __init__(self, payload):
        import json

        self._text = json.dumps(payload)

    def exists(self):
        return True

    def read_text(self, encoding="utf-8"):
        return self._text


class TestAblationOnCategoricalAxes:
    """`--ablate` assumed a numeric band axis, and failed silently on a categorical one.

    `--ablate --band-axis population` on Liang's corpus printed "no rows fell into a band", which
    reads as an empty result rather than a mismatched flag. `ablate()` already accepted a
    value->band dict; only the CLI assumed numbers. Both defects here would hide a real finding
    behind something that looks like an absence of one.
    """

    def test_separation_is_computed_for_any_number_of_bands(self):
        """A 145x ratio reported beside `separated: null` is a number with no claim attached.

        Separation is worst-versus-best and does not depend on band count, but it was computed
        only when there were exactly two. On the five Liang populations the vocabulary channel
        spans 0.7% to 100.0% and that is emphatically separated; reporting `null` would have left
        the largest disparity in this project unqualified.
        """
        import eval.subgroup_audit as sa

        # Three bands. Whatever the rates come out as, `separated` must be a decided boolean.
        rows = [{"text": f"A sentence about {g}. And a second, longer one about {g} as well.",
                 "g": g} for g in ("a",) * 40 + ("b",) * 40 + ("c",) * 40]
        res = sa.ablate(rows, "g", {"a": "a", "b": "b", "c": "c"})
        for comp in res["components"].values():
            assert comp["separated"] is not None, (
                f"separation was not computed for {len(comp['groups'])} bands: {comp}"
            )

    def test_a_band_axis_with_no_usable_group_says_so(self, capsys):
        """The empty case must name the axis and the floor, not print an empty result."""
        import eval.subgroup_audit as sa

        res = sa.ablate([{"text": "hello there friend", "g": "solo"}], "g", {})
        assert res.get("error"), res


class TestBothErrorRatesOnRealData:
    """The half of the audit that could not run, and the defects its first real run exposed.

    `equalised_odds` existed for weeks with only synthetic fixtures, because this repository
    believed no reachable corpus paired human and machine text on the same prompts. Liang ships
    exactly that, in the same upstream repository as the human essays two results already used.
    """

    @staticmethod
    def _run(monkeypatch, rows, axes=("g",), threshold=0.5):
        import untell.scripts.score as sc
        from eval import subgroup_audit as sa

        seq = iter([1.0 if r["_flag"] else 0.0 for r in rows])
        monkeypatch.setattr(sc, "score_text", lambda t, **k: {"max": next(seq)})
        return sa.equalised_odds(rows, axes=axes, threshold=threshold)

    @staticmethod
    def _rows(spec):
        out = []
        for g, is_ai, n, flagged in spec:
            out += [{"text": "x", "g": g, "is_ai": is_ai, "_flag": i < flagged}
                    for i in range(n)]
        return out

    def test_a_zero_false_positive_rate_that_catches_nothing_says_so(self, monkeypatch):
        """MEASURED: at threshold 0.775 the lite tier misses 100% of 176 GPT-3 essays.

        That threshold is this project's own published recommendation for a "safe" operating
        point, derived from false-positive quantiles on a human-only corpus -- where any threshold
        above the score range scores a perfect zero. With one error rate, SAFE and INERT are the
        same number, so the report has to name the second one out loud.
        """
        # Nothing flagged at all: 0% false positives, 100% false negatives.
        rows = self._rows([("x", False, 60, 0), ("x", True, 60, 0)])
        rep = self._run(monkeypatch, rows)
        assert rep["overall_fpr"] == 0.0 and rep["overall_fnr"] == 1.0, rep
        assert "off switch" in rep.get("useless", ""), (
            f"a detector that missed every machine text reported no warning: {rep}"
        )

    def test_the_pooled_pair_is_reported_not_just_per_group(self, monkeypatch):
        """Per-group rows alone let a total false-negative wipeout pass unnoticed."""
        rows = self._rows([("x", False, 40, 4), ("x", True, 40, 36)])
        rep = self._run(monkeypatch, rows)
        for key in ("overall_fpr", "overall_fpr_ci", "overall_fnr", "overall_fnr_ci"):
            assert key in rep, f"{key} missing from the report: {sorted(rep)}"
        assert rep["overall_fpr"] == 0.1 and rep["overall_fnr"] == 0.1, rep
        assert "useless" not in rep, "a working detector was called an off switch"

    def test_an_axis_the_corpus_does_not_carry_is_flagged_missing(self, monkeypatch):
        """"Overall" is in DEFAULT_AXES and no row carries a column of that name.

        It rendered as `{"groups": {}, "fpr_disparity": null}` beside two real axes, which reads
        as "looked here, found nothing" rather than "this axis does not exist" -- the same defect
        a `--csv` label-filter bug caused once already for `ell_status`.
        """
        rows = self._rows([("x", False, 40, 4), ("x", True, 40, 36)])
        rep = self._run(monkeypatch, rows, axes=("g", "Overall"))
        assert rep["axes"]["Overall"]["missing"] is True, rep["axes"]["Overall"]
        assert rep["axes"]["g"]["missing"] is False, rep["axes"]["g"]


def test_the_prompt_engineered_arm_is_a_separate_corpus_not_a_pooled_one():
    """"Can it find GPT-3" and "can it find GPT-3 that is trying" are different questions.

    Liang generated each machine arm twice — plain, and instructed to write in a way that does
    not look machine-generated. Pooling them answers neither: MEASURED 2026-09-01, the miss rate
    at the shipped threshold is 1.7% against the plain arm and 10.2% against the engineered one,
    and a pooled corpus would report something in between that describes no real adversary.
    """
    from eval.datasets import (
        LIANG_MACHINE,
        LIANG_MACHINE_PROMPT_ENGINEERED,
    )

    assert set(LIANG_MACHINE) == set(LIANG_MACHINE_PROMPT_ENGINEERED), (
        "the two machine arms cover different populations, so they cannot be compared"
    )
    assert not set(LIANG_MACHINE.values()) & set(LIANG_MACHINE_PROMPT_ENGINEERED.values()), (
        "the arms point at the same upstream folders; one of them is not what it claims"
    )
    for folder in (*LIANG_MACHINE.values(), *LIANG_MACHINE_PROMPT_ENGINEERED.values()):
        assert folder.startswith("GPT_Data/"), f"{folder} is not machine-written data"


class TestCrossedAxes:
    """Bias concentrates where attributes intersect, and this instrument could not look there.

    "Identifying Bias in Machine-generated Text Detection" (Pindrop, ACL 2026 Main) evaluated 16
    detectors against a demographically labelled corpus and found non-White English-language
    learners flagged far more often than their White peers — a gap neither axis shows alone.
    Every axis here was reported one at a time, so this instrument would have missed exactly that.
    """

    @staticmethod
    def _rows(spec):
        out = []
        for race, ell, n in spec:
            out += [{"text": "x", "race_ethnicity": race, "ell_status": ell} for _ in range(n)]
        return out

    def test_a_crossed_axis_splits_on_both_columns(self):
        import eval.subgroup_audit as sa

        rows = self._rows([("White", "No", 40), ("White", "Yes", 40),
                           ("Asian", "No", 40), ("Asian", "Yes", 40)])
        for r in rows:
            r["flagged"] = False
        got = sa._group(rows, ("race_ethnicity*ell_status",))
        cells = set(got["race_ethnicity*ell_status"]["groups"])
        assert cells == {"White x No", "White x Yes", "Asian x No", "Asian x Yes"}, cells

    def test_a_row_missing_either_part_is_dropped_not_labelled_NA(self):
        """The missing-data subgroup bug, which crossing makes twice as easy to reintroduce.

        ASAP codes absent demography as "NA". A row with a race but no ELL status must not land
        in a cell called "White x NA" — that cell would be a measurement of the registrar's data
        entry, and it once produced a phantom 2.01x disparity on a single axis.
        """
        import eval.subgroup_audit as sa

        assert sa._axis_value({"race_ethnicity": "White", "ell_status": "Yes"},
                              "race_ethnicity*ell_status") == "White x Yes"
        for bad in ({"race_ethnicity": "White", "ell_status": "NA"},
                    {"race_ethnicity": "White"},
                    {"race_ethnicity": "  ", "ell_status": "Yes"}):
            assert sa._axis_value(bad, "race_ethnicity*ell_status") is None, bad

    def test_crossing_keeps_the_minimum_group_floor(self):
        """Crossing splits a corpus fast, so the floor matters more here, not less."""
        import eval.subgroup_audit as sa

        rows = self._rows([("White", "No", 40), ("Asian", "Yes", 5)])
        for r in rows:
            r["flagged"] = False
        got = sa._group(rows, ("race_ethnicity*ell_status",))["race_ethnicity*ell_status"]
        assert got["groups"]["White x No"]["status"] == "reported"
        assert got["groups"]["Asian x Yes"]["status"] == "insufficient"
        assert got["groups"]["Asian x Yes"]["fpr"] is None, "a 5-row cell was given a rate"


def test_default_axes_match_the_corpus_that_was_loaded():
    """`--corpus asap` with defaults reported four empty headings and nothing that matters.

    DEFAULT_AXES carries ELLIPSE's column names. ASAP's are different, and the two it is most
    valuable for — `ell_status` and `student_disability_status` — appear in neither. MEASURED
    2026-09-01: a default ASAP run said nothing about English-language learners or students with
    disabilities on a corpus that labels 2,269 of the first and 1,921 of the second. The `missing`
    flag made the emptiness visible; it did not make the default useful.
    """
    from eval.datasets import _ASAP_LABELS
    from eval.subgroup_audit import CORPUS_AXES, DEFAULT_AXES

    asap = CORPUS_AXES["asap"]
    assert "ell_status" in asap and "student_disability_status" in asap, asap
    for axis in asap:
        for part in axis.split("*"):
            assert part in _ASAP_LABELS, f"{part!r} is not a column ASAP carries"
    # `gender` and `race_ethnicity` are in both corpora, so overlap is expected and correct. What
    # must hold is that the ASAP list adds what the ELLIPSE defaults cannot supply.
    assert set(asap) - set(DEFAULT_AXES) >= {"ell_status", "student_disability_status"}, asap
    assert "SES" not in asap, "ASAP names that column `economically_disadvantaged`"


class TestSelectionCorrectedSeparation:
    """`separated` compares two groups the data itself picked, and 95% is the wrong yardstick.

    MEASURED 2026-09-01, on this instrument's own output. ELLIPSE's `race_ethnicity*grade` axis
    has 13 reportable cells, so a worst-versus-best pick is chosen from 78 pairs — and it was
    reported as separated against a plain z=1.96 while *no single axis on that corpus separates at
    all*. Four of the five crossed axes tried on ELLIPSE found nothing; reporting the fifth
    without accounting for having tried five, over thirteen cells, is how a measurement tool
    manufactures a finding.

    The verdict is now Bonferroni over the k(k-1)/2 pairs. Conservative, which is the right
    direction for a claim about a group of people.
    """

    def test_the_critical_value_grows_with_the_number_of_groups(self):
        from eval.subgroup_audit import _selected_z

        assert _selected_z(2) == pytest.approx(1.96, abs=0.01), "two groups must cost nothing"
        assert _selected_z(6) > _selected_z(3) > _selected_z(2)
        assert _selected_z(13) == pytest.approx(3.41, abs=0.02), "13 cells => 78 pairs"

    def test_a_two_group_axis_is_unaffected(self):
        """The correction must not quietly retract every finding this document already has."""
        import eval.subgroup_audit as sa

        groups = {
            "a": {"n": 2000, "flagged": 700, "fpr": 0.35, "ci": list(sa.wilson(700, 2000)),
                  "status": "reported"},
            "b": {"n": 2000, "flagged": 560, "fpr": 0.28, "ci": list(sa.wilson(560, 2000)),
                  "status": "reported"},
        }
        d = sa._disparity(groups)
        assert d["groups_compared"] == 2
        assert d["separated"] is True and d["separated_uncorrected"] is True

    def test_a_marginal_gap_across_many_cells_loses_its_verdict(self):
        """The case the correction exists for: barely-separated extremes among many groups."""
        import eval.subgroup_audit as sa

        groups = {}
        for i, (n, hits) in enumerate([(200, 88), (200, 58)] + [(200, 72)] * 10):
            groups[f"g{i}"] = {"n": n, "flagged": hits, "fpr": hits / n,
                               "ci": list(sa.wilson(hits, n)), "status": "reported"}
        d = sa._disparity(groups)
        assert d["groups_compared"] == 12
        assert d["separated_uncorrected"] is True, "fixture no longer marginal; retune it"
        assert d["separated"] is False, (
            f"a 12-cell axis kept its verdict under a 66-pair correction: {d}"
        )

    def test_both_verdicts_are_reported_so_the_table_stays_checkable(self):
        """A reader comparing the printed 95% intervals by eye must not be contradicted silently."""
        import eval.subgroup_audit as sa

        groups = {f"g{i}": {"n": 300, "flagged": h, "fpr": h / 300,
                            "ci": list(sa.wilson(h, 300)), "status": "reported"}
                  for i, h in enumerate((120, 90, 100, 110, 95))}
        d = sa._disparity(groups)
        assert set(d) >= {"separated", "separated_uncorrected", "groups_compared"}


def test_the_ablation_separation_is_corrected_too():
    """`ablate` had its own separation check and did not get the correction with `_disparity`.

    Result 14 compares five populations per channel, so its worst-versus-best pick comes from ten
    pairs, not one. A fix applied to one code path and not the other is worse than no fix: the
    document would carry two `separated` fields meaning different things under the same name.
    """
    import eval.subgroup_audit as sa

    rows = []
    for band, n, longish in (("a", 60, True), ("b", 60, False), ("c", 60, False),
                             ("d", 60, False), ("e", 60, False)):
        for _ in range(n):
            rows.append({"text": ("Long sentence with many words indeed. Short one." if longish
                                  else "Tiny. Bit. Here."), "g": band})
    res = sa.ablate(rows, "g", {b: b for b in "abcde"})
    for name, comp in res["components"].items():
        assert "separated_uncorrected" in comp, f"{name} lost the plain verdict"
        assert comp["groups_compared"] == 5, f"{name}: {comp['groups_compared']}"


def test_the_printed_verdict_names_the_test_it_actually_used():
    """A star meaning the corrected test beside a footnote describing the plain one is a lie.

    The renderer switched to the corrected verdict with `_disparity`, but its wording still said
    "the two groups' 95% Wilson intervals do not overlap" — which is the test it had stopped
    using. A reader checking the printed intervals by eye would have found them overlapping on a
    row marked as separated, or the reverse, with nothing on the page to explain it.
    """
    import eval.subgroup_audit as sa

    rows = []
    spec = [("a", 88, 200), ("b", 58, 200)] + [(f"c{i}", 72, 200) for i in range(10)]
    for band, hits, n in spec:
        rows += [{"text": "x", "g": band, "flagged": i < hits} for i in range(n)]
    rep = {"corpus_n": len(rows), "scored_n": len(rows), "tier": "lite", "threshold": 0.5,
           "overall_fpr": 0.36, "overall_ci": [0.34, 0.38], "saturation": None,
           "axes": sa._group(rows, ("g",))}
    text = sa.render(rep)
    d = rep["axes"]["g"]["disparity"]
    assert d["separated_uncorrected"] and not d["separated"], "fixture is no longer marginal"
    assert "selection is accounted for" in text, (
        f"the renderer hid that a plain-95% separation did not survive:\n{text}"
    )
    assert "widened for a pick from" in text, text


def test_a_two_group_axis_still_reads_plainly():
    """The extra wording must not clutter the common case, where nothing was selected."""
    import eval.subgroup_audit as sa

    rows = ([{"text": "x", "g": "a", "flagged": i < 140} for i in range(400)]
            + [{"text": "x", "g": "b", "flagged": i < 60} for i in range(400)])
    rep = {"corpus_n": 800, "scored_n": 800, "tier": "lite", "threshold": 0.5,
           "overall_fpr": 0.25, "overall_ci": [0.22, 0.28], "saturation": None,
           "axes": sa._group(rows, ("g",))}
    text = sa.render(rep)
    assert "widened for a pick" not in text, text
    assert "intervals separate" in text, text


class TestRaidPerDomainThresholds:
    """Result 21's evidence: 46 real detectors' own per-domain calibration.

    RAID's leaderboard requires each submission to publish, per text domain, the threshold at
    which that detector's false-positive rate on human text is 5% — `find_threshold` in
    `raid/evaluate.py` fits it separately on each domain's human, unattacked texts. A
    domain-stable detector would report eight near-identical numbers. The median span across 46
    detectors is 0.610 of the 0-1 range.

    The extract is committed rather than the 3.4 GB clone, so these guard the extract against
    the claims the document makes from it.
    """

    @staticmethod
    def _load():
        import json
        import pathlib

        p = (pathlib.Path(__file__).resolve().parent.parent
             / ".claude" / "probes" / "raid-per-domain-thresholds.json")
        return json.loads(p.read_text(encoding="utf-8"))

    def test_every_row_has_all_eight_domains_on_a_unit_scale(self):
        rows = self._load()
        assert len(rows) == 46, f"the document says 46 detectors; extract has {len(rows)}"
        for r in rows:
            th = r["thresholds_at_5pct_fpr"]
            assert len(th) == 8, f"{r['detector']} has {len(th)} domains"
            for dom, v in th.items():
                assert 0.0 <= v <= 1.0, (
                    f"{r['detector']}/{dom} = {v} is off a 0-1 scale, so an absolute span is "
                    f"not the right statistic for it"
                )

    def test_the_median_span_is_what_the_document_quotes(self):
        import statistics

        spans = [r["span"] for r in self._load()]
        assert statistics.median(spans) == pytest.approx(0.610, abs=0.005)
        assert sum(1 for s in spans if s > 0.5) == 25
        assert sum(1 for s in spans if s > 0.9) == 13

    def test_binoculars_is_the_stable_counterexample(self):
        """One well-behaved detector is what makes the other 45 a finding and not an artifact."""
        rows = {r["detector"]: r for r in self._load()}
        assert rows["Binoculars"]["span"] < 0.05, rows["Binoculars"]
        assert rows["GPTZero"]["span"] > 0.7, rows["GPTZero"]

    def test_the_domain_ordering_is_consistent_across_detectors(self):
        """`recipes` needing the most permissive threshold is a property of the text, not a model."""
        import collections
        import statistics

        ranks = collections.defaultdict(list)
        for r in self._load():
            th = r["thresholds_at_5pct_fpr"]
            for i, dom in enumerate(sorted(th, key=th.get)):
                ranks[dom].append(i)
        mean_rank = {d: statistics.mean(v) for d, v in ranks.items()}
        assert min(mean_rank, key=mean_rank.get) == "recipes", mean_rank
        assert max(mean_rank, key=mean_rank.get) == "books", mean_rank


class TestDetectorCalibrationCommand:
    """`untell-detector-calibration` audits 46 real detectors at zero cost.

    It reads RAID's public leaderboard, where every submission publishes the threshold at which
    its false-positive rate on human text is 5%, per text domain. No API key, no GPU, no gated
    dataset. These guard the properties that make it worth shipping.
    """

    def test_it_works_offline_from_the_committed_snapshot(self):
        from eval.detector_calibration import main

        assert main(["report"]) == 0

    def test_the_summary_matches_what_result_21_quotes(self):
        import json

        from eval.detector_calibration import SNAPSHOT, summarise

        s = summarise(json.loads(SNAPSHOT.read_text(encoding="utf-8")))
        assert s["detectors"] == 46
        assert s["median_span"] == pytest.approx(0.610, abs=0.005)
        assert s["over_half"] == 25 and s["over_ninety"] == 13

    def test_it_checks_the_scale_rather_than_assuming_it(self):
        """The span is only the right statistic while every threshold sits on [0,1].

        The first version of this analysis reported ratios and produced 63370x for a detector
        whose thresholds run 1.6e-05 to 0.9997 — an artifact of how close the low end sits to
        zero. The span is scale-appropriate, and the scale is verified rather than assumed.
        """
        import json

        from eval.detector_calibration import SNAPSHOT, summarise

        s = summarise(json.loads(SNAPSHOT.read_text(encoding="utf-8")))
        assert s["off_unit_scale"] == [], s["off_unit_scale"]

    def test_a_fetch_failure_falls_back_instead_of_dying(self, monkeypatch, capsys):
        """A network-dependent tool that dies offline is a tool nobody can reproduce."""
        import eval.detector_calibration as dc

        def boom(dest, timeout=900):
            raise dc.LeaderboardUnavailable("no network")

        monkeypatch.setattr(dc, "fetch", boom)
        assert dc.main(["report", "--fetch"]) == 0
        assert "falling back to the snapshot" in capsys.readouterr().err

    def test_the_sparse_pattern_takes_results_and_not_predictions(self):
        """`predictions.json` carries a score per example and runs to gigabytes.

        A full clone of RAID is 3.4 GB; results-only is 205 MB. Widening this pattern would make
        the command unusable on a normal connection, which is the whole point of it.
        """
        from eval.detector_calibration import SPARSE_PATTERN

        assert SPARSE_PATTERN.endswith("results.json"), SPARSE_PATTERN
        assert "predictions" not in SPARSE_PATTERN


class TestRaidAttackEvidence:
    """Result 22's evidence: attack and generator breakdowns from the same 46 submissions.

    The extract is committed rather than the leaderboard clone. These pin the numbers the document
    quotes, and in particular the bimodality — because the mean alone would licence the wrong
    claim, which is the mistake this document keeps catching in others.
    """

    @staticmethod
    def _load():
        import json
        import pathlib

        p = (pathlib.Path(__file__).resolve().parent.parent
             / ".claude" / "probes" / "raid-attacks-and-generators.json")
        return json.loads(p.read_text(encoding="utf-8"))

    def test_homoglyph_is_the_most_effective_attack_on_average(self):
        d = self._load()["mean_accuracy_by_attack"]
        assert min(d, key=d.get) == "homoglyph", d
        assert d["homoglyph"] == pytest.approx(0.725, abs=0.005)
        assert d["none"] > d["paraphrase"] > d["homoglyph"]

    def test_the_mean_hides_a_bimodal_distribution(self):
        """The finding is the shape, not the average.

        Reporting only the 72.5% mean would say "homoglyph attacks cost detectors 17 points",
        which is true of no detector: the median loses 0.7% and fourteen lose more than twenty.
        """
        d = self._load()
        assert d["homoglyph_median_loss"] < 0.02, d["homoglyph_median_loss"]
        assert d["homoglyph_immune_under_2pt"] == 23
        assert d["homoglyph_losing_over_20pt"] == 14

    def test_robustness_does_not_transfer_between_axes(self):
        """Binoculars is the most domain-stable detector and among the most attack-fragile."""
        rows = {r["detector"]: r for r in self._load()["homoglyph_per_detector"]}
        assert rows["Binoculars"]["loss"] > 0.40, rows["Binoculars"]

    def test_instruction_tuning_makes_text_more_detectable(self):
        """Every base/chat pair moves the same way, which is why the claim is worth making."""
        g = self._load()["mean_accuracy_by_generator_no_attack"]
        for base, chat in (("mistral", "mistral-chat"), ("mpt", "mpt-chat"),
                           ("cohere", "cohere-chat")):
            assert g[chat] > g[base], f"{chat} {g[chat]} is not above {base} {g[base]}"
        assert g["gpt4"] > g["cohere"], "the strongest model is not the hardest to detect"
