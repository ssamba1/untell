"""Inference-only ceiling measurement tests — offline (baseline + stub-rewriter delta)."""

from __future__ import annotations

import re

from eval.ceiling import _SAMPLE, main, measure_ceiling


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
            sentinels = re.findall(r"⟦HZ\d{4}⟧", text)
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
