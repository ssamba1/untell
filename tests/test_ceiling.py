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
