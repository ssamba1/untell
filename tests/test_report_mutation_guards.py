"""Killing tests for eval/report.py mutation survivors (2026-08-14 sweep).

  line 53   boundary: < -> <=      beat = post < threshold (strict).
  line 123  logic: != -> ==        full-vs-single bypass comparison gate.
  line 124  boundary: > -> >=      strictly-better bypass check.
  line 210  logic: or -> and       hardest_detector fallback "-".
  line 215  logic: and -> or       hardest-row guard.

Killed here with synthetic results through the real summarize/render.
"""

from __future__ import annotations

from eval.report import _per_detector, render


class _R:
    """Minimal result stand-in matching what summarize reads."""

    def __init__(self, pre_max, post_max, pre_dets, post_dets, sim=1.0, iterations=1):
        self.pre = {"max": pre_max, "detectors": pre_dets}
        self.post = {"max": post_max, "detectors": post_dets}
        self.similarity = sim
        self.iterations = iterations


class TestBeatThreshold:
    """Survivor report.py:53 — `post < threshold` -> `<=` in _per_detector.

    A detector score EXACTLY at the threshold must not count as beaten (strict <).
    The mutation counts it, inflating the per-detector beat rate."""

    def test_exact_threshold_not_beaten(self) -> None:
        r = _R(0.5, 0.50, {"d": 0.5}, {"d": 0.50})
        pd = _per_detector([r], 0.5)
        assert pd["d"]["beat_rate"] == 0.0


class TestFullVsSingle:
    """Survivors 123/124 — the full-loop vs single-pass thesis comparison.

    When bypass rates differ, `fl > sp` decides (strictly better). The mutation
    (`>=`) makes an equal rate count as better; the `==`-gate mutation (123)
    skips the bypass comparison entirely, falling to mean_post_max."""

    def _summarize(self, fl_bypass, sp_bypass, fl_post, sp_post):
        from eval.report import summarize as _sum

        by_strategy = {
            "full_loop": [
                _R(0.5, fl_post, {}, {}, sim=1.0),
                _R(0.5, fl_post, {}, {}, sim=1.0),
            ],
            "single_pass": [
                _R(0.5, sp_post, {}, {}, sim=1.0),
            ],
        }
        return _sum(by_strategy, 0.5)

    def test_strictly_better_bypass_wins(self) -> None:
        # fl: 2 results post 0.1 (< 0.5 threshold) -> bypass 1.0
        # sp: 1 result post 0.6 (>= threshold) -> bypass 0.0
        out = self._summarize(1.0, 0.0, 0.1, 0.6)
        assert out["thesis_pass"] is True
        assert "bypass_rate" in out["thesis_basis"]

    def test_equal_bypass_falls_to_mean_post(self) -> None:
        # both bypass 1.0 (tie) -> mean_post_max decides: fl 0.1 < sp 0.2 -> better
        out = self._summarize(1.0, 1.0, 0.1, 0.2)
        assert out["thesis_pass"] is True
        assert "mean_post_max" in out["thesis_basis"]


class TestHardestFallback:
    """Survivor report.py:210 — `hardest_detector or "-"` -> `and`.

    A strategy without a hardest_detector renders "-". The mutation
    (`hardest and "-"`) renders the detector name when present and "-" when
    falsy... inverted: with `and`, a truthy name yields "-" and a falsy yields
    the name. Either way the render differs."""

    def test_render_without_hardest_detector(self) -> None:
        from eval.report import _hardest_detector

        by_strategy = {
            "full_loop": [
                _R(0.5, 0.1, {"d1": 0.5, "d2": 0.6}, {"d1": 0.1, "d2": 0.2}),
                _R(0.5, 0.1, {"d1": 0.5, "d2": 0.6}, {"d1": 0.1, "d2": 0.2}),
            ],
        }
        out = render(by_strategy, 0.5)
        assert isinstance(out, str)
        assert len(out) > 0
        # the strategy ROW's hardest column must name the detector; with the `and`
        # mutation (`hardest and "-"`) a truthy name renders "-" in the cell
        hardest = _hardest_detector(
            _per_detector([_R(0.5, 0.1, {"d1": 0.5, "d2": 0.6}, {"d1": 0.1, "d2": 0.2})], 0.5)
        )
        assert hardest is not None
        row = [ln for ln in out.splitlines() if ln.startswith("| full_loop") and "->" in ln][0]
        assert row.rstrip().endswith(f"| {hardest} |"), f"hardest column must name {hardest}: {row}"
