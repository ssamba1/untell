"""Inference-only ceiling measurement tests — offline (baseline + stub-rewriter delta)."""

from __future__ import annotations

import pytest

from eval.ceiling import _SAMPLE, main, measure_ceiling


class TestTheCorpusIsPartOfTheResult:
    """A ceiling is a property of the corpus as much as of the loop.

    The built-in sample is three HAND-WRITTEN paragraphs. They read as AI but start at mean max
    P(AI) 0.859, where real ChatGPT answers start at 0.998, and at IDENTICAL length the loop lands
    at 0.234 on them (0% still flagged) against 0.628 on HC3 (50% still flagged). The result
    carried no record of which corpus produced it, so a demo number and a benchmark number were
    indistinguishable once written down.
    """

    def test_the_result_names_its_corpus(self):
        from eval.ceiling import measure_ceiling

        r = measure_ceiling(["Some text to score here and there."], tier="lite", max_iters=1)
        assert r["corpus"] == "builtin"
        assert r["corpus_mean_words"] == 7

    def test_a_caller_can_label_its_own_corpus(self):
        from eval.ceiling import measure_ceiling

        r = measure_ceiling(["a b c d e"], tier="lite", max_iters=1, corpus="hc3")
        assert r["corpus"] == "hc3"

    def test_the_render_warns_only_for_the_builtin_sample(self):
        from eval.ceiling import _render, measure_ceiling

        builtin = _render(measure_ceiling(["a b c"], tier="lite", max_iters=1))
        real = _render(measure_ceiling(["a b c"], tier="lite", max_iters=1, corpus="hc3"))
        assert "hand-written" in builtin
        assert "hand-written" not in real

    def test_the_render_states_the_corpus_on_the_header_line(self):
        from eval.ceiling import _render, measure_ceiling

        out = _render(measure_ceiling(["a b c"], tier="lite", max_iters=1, corpus="hc3"))
        assert "corpus=hc3" in out.splitlines()[0]


def test_dataset_flag_refuses_to_report_a_fallback_under_a_real_name(monkeypatch, capsys):
    """load_samples substitutes the built-in sample when `datasets` is missing or the load fails.

    Reporting that as an hc3 ceiling would attach real-corpus authority to the demo corpus — the
    exact confusion the corpus field exists to prevent.
    """
    import eval.ceiling as ceiling
    import eval.datasets as datasets

    def _unavailable(dataset="builtin", n=5, strict=False):
        assert strict, "the ceiling CLI must ask for the dataset strictly"
        raise datasets.DatasetUnavailable(f"dataset {dataset!r} is unavailable (test)")

    monkeypatch.setattr(datasets, "load_samples", _unavailable)
    rc = ceiling.main(["--dataset", "hc3", "--n", "3", "--tier", "lite", "--max-iters", "1"])
    assert rc == 1
    assert "unavailable" in capsys.readouterr().out


class TestStrictLoadingRefusesToSubstitute:
    """A silent fallback puts a demo corpus's numbers under a real corpus's name.

    The built-in sample is three hand-written paragraphs, measurably easier than real AI output
    (Result 10), so this is not a cosmetic mislabel — it is the difference between "flagged 0.00"
    and "flagged 1.00". Every caller that PRINTS a dataset name now loads strictly.
    """

    def test_a_bad_name_raises_instead_of_substituting(self):
        from eval.datasets import DatasetUnavailable, load_samples

        with pytest.raises(DatasetUnavailable, match="no such dataset"):
            load_samples("not-a-dataset", 2, strict=True)

    def test_the_default_still_falls_back_quietly_enough_for_a_smoke_run(self):
        from eval.datasets import load_samples

        assert len(load_samples("not-a-dataset", 2)) == 2

    def test_builtin_is_never_strict(self):
        from eval.datasets import load_samples

        assert len(load_samples("builtin", 2, strict=True)) == 2

    @pytest.mark.parametrize(
        ("module", "func", "kwargs"),
        [
            ("training.distill", "distill", {"dataset": "not-a-dataset", "n": 1, "tier": "lite"}),
            ("training.rl_humanizer", "build_dataset", {"name": "not-a-dataset", "n": 1}),
        ],
    )
    def test_the_training_entry_points_load_strictly(self, module, func, kwargs):
        import importlib

        from eval.datasets import DatasetUnavailable

        mod = importlib.import_module(module)
        with pytest.raises(DatasetUnavailable):
            getattr(mod, func)(**kwargs)


def test_baseline_without_rewriter():
    # No rewriter and no API key => baseline (pre) only; post is None but the run still succeeds.
    r = measure_ceiling(_SAMPLE[:2], tier="lite", max_iters=2, rewriter=None)
    assert r["n"] == 2
    assert r["rewriter_available"] is False
    assert r["pre_flagged_rate"] is not None
    assert r["post_flagged_rate"] is None
    assert r["pre_mean_max"] is not None


def test_full_delta_with_stub_rewriter():
    class _RW:
        name = "stub"

        def available(self):
            return True

        def rewrite(self, text, score_result, threshold=0.30):
            # Production pattern, not a hand-written `\d{4}` — see tests/test_run.py.
            from untell.scripts.preserve import SENTINEL_RE

            sentinels = SENTINEL_RE.findall(text)
            return "Plain, short, human line. " + " ".join(sentinels)

    r = measure_ceiling(_SAMPLE[:2], tier="lite", threshold=0.30, max_iters=2, rewriter=_RW())
    assert r["rewrote"] == 2
    assert r["rewriter_available"] is True
    assert r["post_flagged_rate"] is not None
    assert r["pre_mean_max"] is not None and r["post_mean_max"] is not None
    assert isinstance(r["per_detector_pre"], dict) and r["per_detector_pre"]


def test_cli_smoke(capsys):
    rc = main(["--tier", "lite", "--max-iters", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ceiling" in out.lower()
    assert "flagged rate" in out.lower()


def test_repeats_records_per_run_means_and_spread(monkeypatch):
    """The free rewriters are randomized, so a single pass is not reproducible evidence.

    `repeats` must re-run the whole corpus N times and report the per-run means plus their stdev,
    so a quoted number can be read with its error bar."""
    import eval.ceiling as C

    runs = {"n": 0}

    def _fake_score(t, tier="full", threshold=0.3):
        # rewritten text alternates 0.2 / 0.4 per run so the spread is non-zero
        if "REW" not in t:
            m = 0.9
        else:
            m = 0.2 if runs["n"] % 2 else 0.4
        return {"max": m, "mean": m, "detectors": {"d": m}, "tier": tier,
                "threshold": threshold, "flagged": m >= threshold}

    def _fake_untell(t, **kw):
        out = t + " REW"
        return {"final": out, "pre": _fake_score(t), "post": _fake_score(out), "stopped": "passed"}

    def _fake_run(t, **kw):
        res = _fake_untell(t, **kw)
        return res

    monkeypatch.setattr(C, "score_text", _fake_score)
    monkeypatch.setattr(C, "untell_text", _fake_run)

    r = C.measure_ceiling(["para one", "para two"], repeats=3)
    assert r["repeats"] == 3
    assert len(r["run_post_means"]) == 3       # one mean recorded per run
    assert r["post_mean_max_stdev"] is not None
    assert "across 3 runs" in C._render(r)     # the spread is surfaced, not hidden


def test_repeats_default_is_single_run_without_spread():
    import eval.ceiling as C

    assert C._stdev([0.5]) is None       # a single sample has no spread
    assert C._stdev([]) is None
    assert C._stdev([0.2, 0.4]) == 0.1   # population stdev


def test_reports_meaning_similarity_alongside_evasion(monkeypatch):
    """A ceiling number is meaningless without the fidelity it cost: a rewrite that destroys the
    text trivially beats every detector. mean/min similarity must be reported and rendered."""
    import eval.ceiling as C

    def _fake_score(t, tier="full", threshold=0.3):
        m = 0.9 if "REW" not in t else 0.1
        return {"max": m, "mean": m, "detectors": {"d": m}, "tier": tier,
                "threshold": threshold, "flagged": m >= threshold}

    def _fake_run(t, **kw):
        out = t + " REW"
        return {"final": out, "pre": _fake_score(t), "post": _fake_score(out),
                "similarity": 0.93, "stopped": "passed"}

    monkeypatch.setattr(C, "score_text", _fake_score)
    monkeypatch.setattr(C, "untell_text", _fake_run)

    r = C.measure_ceiling(["para one", "para two"], repeats=2)
    assert r["mean_similarity"] == 0.93
    assert r["min_similarity"] == 0.93
    assert "meaning preserved" in C._render(r)


def test_rewrote_denominator_counts_every_attempt(monkeypatch):
    """`rewrote` accumulates across ALL repeats; `n` is one run's corpus size. Printing
    `rewrote/n` therefore rendered a success count LARGER than the total it was measured
    against — "(rewrote 9/3)" at --repeats 3, "(rewrote 27/3)" at --repeats 9 — on the line
    carrying the headline result."""
    import eval.ceiling as C

    base = {
        "n": 3, "tier": "full", "threshold": 0.3, "max_iters": 2, "best_of": 3,
        "run_post_means": None, "post_mean_max_stdev": None,
        "mean_similarity": 0.93, "min_similarity": 0.82, "rewriter_available": True,
        "pre_flagged_rate": 1.0, "post_flagged_rate": 0.148,
        "pre_mean_max": 0.8587, "post_mean_max": 0.2613,
        "per_detector_pre": {"d1": 0.6}, "per_detector_post": {"d1": 0.19},
    }

    single = C._render({**base, "repeats": 1, "rewrote": 3})
    assert "(rewrote 3/3)" in single

    repeated = C._render({
        **base, "repeats": 9, "rewrote": 27,
        "run_post_means": [0.25] * 9, "post_mean_max_stdev": 0.027,
    })
    assert "(rewrote 27/27)" in repeated, repeated
    assert "27/3" not in repeated, "the denominator is still one run's corpus size"


def test_render_survives_a_missing_repeats_key():
    """_render is called on dicts built by callers and by tests; a missing/None repeats must not
    crash the report or divide by zero."""
    import eval.ceiling as C

    out = C._render({
        "n": 2, "tier": "lite", "threshold": 0.3, "max_iters": 1, "best_of": 1,
        "rewrote": 2, "rewriter_available": True,
        "pre_flagged_rate": 1.0, "post_flagged_rate": 0.5,
        "pre_mean_max": 0.8, "post_mean_max": 0.3,
        "per_detector_pre": {}, "per_detector_post": {},
    })
    assert "(rewrote 2/2)" in out


class TestTheResultNamesItsRewriter:
    """A ceiling is a property of the rewriter as much as of the corpus.

    MEASURED, same corpus and settings, only --rewriter changed:
        composite   0.999 -> 0.860   flagged 1.00   hc3_roberta 0.810
        neural      0.999 -> 0.502   flagged 0.50   hc3_roberta 0.407
    The repo's headline real-text figure was recorded without naming the rewriter and was then
    read as a property of the free TIER. `rewriter_available` records only THAT one ran.
    """

    TEXT = ["Moreover, we leverage robust solutions. Furthermore, this underscores the pivotal role."]

    def test_rewriter_name_is_recorded(self, monkeypatch):
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        from eval.ceiling import measure_ceiling
        from untell.rewriter import get_rewriter

        r = measure_ceiling(
            self.TEXT, tier="lite", rewriter=get_rewriter(prefer="composite"),
            best_of=1, max_iters=1, corpus="probe",
        )
        assert r["rewriter"] == "composite"

    def test_an_alias_is_recorded_as_what_actually_ran(self, monkeypatch):
        """--rewriter max builds an EnsembleRewriter, so the result must say 'ensemble'.

        Recording the user's string would put two names on one method in the record, which is
        how 'max 0.748 vs ensemble 0.485' looked like two data points instead of one method's
        run-to-run spread.
        """
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        from eval.ceiling import measure_ceiling
        from untell.rewriter import get_rewriter

        for alias in ("max", "ensemble"):
            r = measure_ceiling(
                self.TEXT, tier="lite", rewriter=get_rewriter(prefer=alias),
                best_of=1, max_iters=1, corpus="probe",
            )
            assert r["rewriter"] == "ensemble", f"{alias} recorded as {r['rewriter']!r}"

    def test_no_rewriter_records_none_not_a_guess(self, monkeypatch):
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        from eval.ceiling import measure_ceiling

        r = measure_ceiling(
            self.TEXT, tier="lite", rewriter=None, best_of=1, max_iters=1, corpus="probe"
        )
        assert r["rewriter"] is None

    def test_render_shows_the_rewriter_in_the_header(self, monkeypatch):
        """The banner is where these numbers are actually read."""
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        from eval.ceiling import _render, measure_ceiling
        from untell.rewriter import get_rewriter

        r = measure_ceiling(
            self.TEXT, tier="lite", rewriter=get_rewriter(prefer="composite"),
            best_of=1, max_iters=1, corpus="probe",
        )
        assert "rewriter=composite" in _render(r).splitlines()[0]


def test_an_unknown_name_is_diagnosed_as_a_name_even_without_the_datasets_extra():
    """The name is checked before the dependency.

    A typo used to be reported as "the `datasets` package is not installed" on any machine without
    the eval extra — true, but it names the wrong problem. The user installs the extra, runs the
    same command, and fails again for the reason nobody mentioned. The known set is a constant, so
    the diagnosis is available either way.
    """
    from eval.datasets import DatasetUnavailable, load_samples

    with pytest.raises(DatasetUnavailable, match="no such dataset"):
        load_samples("not-a-dataset", 2, strict=True)


def test_a_known_name_still_reports_the_missing_dependency():
    """The name check must not swallow the real diagnosis for a name that IS known."""
    import builtins

    import pytest as _pytest

    from eval.datasets import DatasetUnavailable, load_samples

    real_import = builtins.__import__

    def no_datasets(name, *a, **k):
        if name == "datasets":
            raise ImportError("no datasets here")
        return real_import(name, *a, **k)

    builtins.__import__ = no_datasets
    try:
        with _pytest.raises(DatasetUnavailable, match="not installed"):
            load_samples("hc3", 2, strict=True)
    finally:
        builtins.__import__ = real_import
