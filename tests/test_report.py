"""Benchmark report tests (lite, builtin)."""

from __future__ import annotations

from eval.benchmark import run
from eval.report import _bypass_rate, render, summarize


def _by():
    return run("builtin", 4, "lite", 0.30, ["noop", "single_pass", "full_loop"])


def test_summarize_shape():
    s = summarize(_by(), 0.30)
    assert set(s["strategies"]) == {"noop", "single_pass", "full_loop"}
    for st in s["strategies"].values():
        assert st["n"] == 4
        assert 0.0 <= st["bypass_rate"] <= 1.0
        assert 0.0 <= st["mean_similarity"] <= 1.0
        assert "perplexity_burstiness" in st["per_detector"]
        pd = st["per_detector"]["perplexity_burstiness"]
        assert 0.0 <= pd["pre"] <= 1.0 and 0.0 <= pd["post"] <= 1.0
    assert "thesis_pass" in s and isinstance(s["thesis_pass"], bool)


def test_render_is_ascii_safe_and_complete():
    md = render(_by(), 0.30)
    md.encode("ascii")  # no emoji -> never crashes a Windows cp1252 console
    assert "# untell benchmark" in md
    assert "Per-detector" in md
    assert "Thesis" in md


def test_per_detector_has_beat_rate_and_hardest():
    s = summarize(_by(), 0.30)
    for st in s["strategies"].values():
        pd = st["per_detector"]["perplexity_burstiness"]
        assert 0.0 <= pd["beat_rate"] <= 1.0
        assert "hardest_detector" in st
    # with only the lite detector present, it must be the hardest
    assert s["strategies"]["noop"]["hardest_detector"] == "perplexity_burstiness"


def test_render_shows_beat_and_hardest():
    md = render(_by(), 0.30)
    assert "beat%" in md
    assert "Hardest detector" in md


def test_bypass_rate_empty_is_zero():
    assert _bypass_rate([], 0.30) == 0.0


def test_noop_is_identity():
    # noop never changes the text, so pre==post and similarity is perfect — true at any tier
    # (the lite perplexity detector auto-upgrades to GPT-2 when torch is present, so the absolute
    # bypass rate is environment-dependent and must not be asserted to an exact value).
    s = summarize(run("builtin", 3, "lite", 0.30, ["noop"]), 0.30)
    noop = s["strategies"]["noop"]
    assert noop["mean_pre_max"] == noop["mean_post_max"]
    assert noop["mean_similarity"] == 1.0
    assert 0.0 <= noop["bypass_rate"] <= 1.0


def test_unscored_samples_are_not_counted_as_bypasses():
    """score_text returns max: 0.0 as a PLACEHOLDER when no detector produced a number, and
    0.0 < threshold is true - so a benchmark run against a broken ML stack reported a 100%
    bypass rate, the most flattering number available, produced by measuring nothing."""
    from eval.report import _bypass_rate

    class _R:
        def __init__(self, post):
            self.post = post
            self.pre = post

    unscored = {"max": 0.0, "scored": False, "detectors": {}}
    scored_pass = {"max": 0.10, "detectors": {"d": 0.10}}
    scored_fail = {"max": 0.90, "detectors": {"d": 0.90}}

    assert _bypass_rate([_R(unscored)] * 4, 0.30) == 0.0, "unscored counted as a clean pass"
    assert _bypass_rate([_R(scored_pass), _R(scored_fail)], 0.30) == 0.5
    # Unscored samples are excluded from the denominator too, not counted as failures.
    assert _bypass_rate([_R(scored_pass), _R(unscored)], 0.30) == 1.0


class TestOneDenominatorPerRow:
    """Every P(AI) figure in a strategy row must be over the same sample set.

    `_bypass_rate` already excluded unscored samples — `max: 0.0` is a placeholder and
    `0.0 < threshold` would count it as a pass — but the means beside it did not, and the `n`
    column showed the full count. Three published figures over two different populations, in one
    row, with nothing saying so.
    """

    @staticmethod
    def _r(pre_max, post_max, scored=True, sim=0.95):
        from dataclasses import dataclass, field

        @dataclass
        class _R:
            pre: dict
            post: dict
            similarity: float = 0.95
            iterations: int = 1
            text: str = "x"
            history: list = field(default_factory=list)

        post = ({"max": post_max, "mean": post_max, "detectors": {"d": post_max}, "scored": True}
                if scored else {"max": 0.0, "mean": 0.0, "detectors": {}, "scored": False})
        return _R(
            pre={"max": pre_max, "mean": pre_max, "detectors": {"d": pre_max}, "scored": True},
            post=post, similarity=sim,
        )

    def test_mean_post_max_excludes_unscored_placeholders(self):
        """Measured: 5 samples at 0.35 plus 5 unscored gave mean_post_max 0.175 — comfortably under
        a 0.30 threshold, so the strategy read as succeeding — next to a bypass rate of 0%."""
        from eval.report import summarize

        rows = [self._r(0.9, 0.35) for _ in range(5)] + [self._r(0.9, 0.0, scored=False) for _ in range(5)]
        st = summarize({"test": rows}, 0.30)["strategies"]["test"]
        assert abs(st["mean_post_max"] - 0.35) < 1e-9, st["mean_post_max"]
        assert st["n"] == 10 and st["n_scored"] == 5

    def test_thesis_is_not_declared_on_incomparable_denominators(self):
        """The project's headline claim. Measured: full_loop with 1 pass and 9 unscored reported a
        100% bypass rate against single_pass's genuine 50% (5 of 10), and the thesis "passed" — while
        single_pass was five times better in absolute terms."""
        from eval.report import summarize

        by = {
            "full_loop": [self._r(0.9, 0.1)] + [self._r(0.9, 0.0, scored=False) for _ in range(9)],
            "single_pass": [self._r(0.9, 0.1) for _ in range(5)] + [self._r(0.9, 0.9) for _ in range(5)],
        }
        s = summarize(by, 0.30)
        assert s["thesis_pass"] is False
        assert "thesis_undecided" in s

    def test_thesis_still_passes_when_everything_scored(self):
        """The guard must not make the thesis unprovable."""
        from eval.report import summarize

        by = {
            "full_loop": [self._r(0.9, 0.1) for _ in range(8)] + [self._r(0.9, 0.9) for _ in range(2)],
            "single_pass": [self._r(0.9, 0.1) for _ in range(5)] + [self._r(0.9, 0.9) for _ in range(5)],
        }
        s = summarize(by, 0.30)
        assert s["thesis_pass"] is True
        assert "thesis_undecided" not in s

    def test_table_shows_the_real_denominator(self):
        from eval.report import render

        rows = [self._r(0.9, 0.35) for _ in range(5)] + [self._r(0.9, 0.0, scored=False) for _ in range(5)]
        out = render({"test": rows}, 0.30)
        assert "| 5/10 |" in out, out
        assert "scored/total" in out

    def test_table_stays_clean_when_nothing_is_unscored(self):
        from eval.report import render

        out = render({"test": [self._r(0.9, 0.1) for _ in range(4)]}, 0.30)
        assert "| 4 |" in out
        assert "scored/total" not in out
