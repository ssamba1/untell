"""score.py tests — must run in lite tier with zero ML installed, emit valid JSON."""

from __future__ import annotations

import json

from untell.scripts.score import main, score_text


def test_score_text_shape_lite():
    result = score_text("Moreover, this is a formulaic test sentence.", tier="lite", threshold=0.3)
    assert result["tier"] == "lite"
    assert "detectors" in result and result["detectors"]
    assert 0.0 <= result["max"] <= 1.0
    assert 0.0 <= result["mean"] <= 1.0
    assert isinstance(result["flagged"], bool)
    assert result["flagged"] == (result["max"] >= result["threshold"])


def test_score_text_lite_detector_present():
    result = score_text("Some text to score.", tier="lite")
    assert "perplexity_burstiness" in result["detectors"]


def test_cli_emits_valid_json(capsys):
    rc = main(["Furthermore, the system performs adequately overall.", "--tier", "lite"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["tier"] == "lite"
    assert "max" in parsed


def test_cli_empty_input(capsys):
    rc = main(["   ", "--tier", "lite"])
    assert rc == 2
    parsed = json.loads(capsys.readouterr().out)
    assert "error" in parsed


def test_full_tier_request_runs_without_torch():
    # Requesting 'full' with no ML installed must not raise; degrades to lite.
    result = score_text("Test text here.", tier="full")
    assert result["tier"] in ("lite", "full", "heavy")
    assert 0.0 <= result["max"] <= 1.0


def test_dead_detectors_excluded_not_pinned_at_half(monkeypatch):
    """Regression: a full detector that fails to load must be EXCLUDED from the aggregate,
    never folded in as a neutral 0.5 (the real-world bug where a broken NumPy env pinned max=0.5
    and the report falsely claimed the full tier ran)."""
    import untell.scripts.score as score_mod

    class GoodLite:
        name, tier = "perplexity_burstiness", "lite"

        def available(self):
            return True

        def score(self, text):
            return 0.1

    class Broken:  # mimics mage/hc3 crashing on a NumPy 2.x mismatch
        name, tier = "mage", "full"

        def available(self):
            return True

        def score(self, text):
            raise RuntimeError("simulated NumPy 2.x crash")

    class NoSignal:  # mimics a detector that returns None (e.g. text too short)
        name, tier = "hc3_roberta", "full"

        def available(self):
            return True

        def score(self, text):
            return None

    monkeypatch.setattr(score_mod, "load_detectors", lambda tier="full": [GoodLite(), Broken(), NoSignal()])
    r = score_mod.score_text("some text", tier="full", threshold=0.3)

    assert r["max"] == 0.1, "max must reflect only the live detector, not a 0.5 from a dead one"
    assert r["detectors"]["mage"] is None
    assert r["detectors"]["hc3_roberta"] is None
    assert r["tier"] == "lite", "tier must report what actually scored, not what was selected"
    assert "mage" in r.get("failed_detectors", [])
    assert "warning" in r
    assert r["flagged"] is False  # 0.1 < 0.3


def _fake_detectors(values):
    """Install detectors returning exactly `values` (an Exception instance means it raises)."""
    class _D:
        def __init__(self, name, v):
            self.name, self.tier, self._v = name, "lite", v

        def available(self):
            return True

        def score(self, text):
            if isinstance(self._v, Exception):
                raise self._v
            return self._v

    return lambda tier="lite": [_D(f"d{i}", v) for i, v in enumerate(values)]


def test_out_of_range_score_is_clamped_and_surfaced(monkeypatch):
    """A detector is supposed to return P(AI) in [0,1]; three adapters shipped wrong values this
    session. Out-of-range output does real damage: a 0-100 scale makes ai_percent read 8500.0, and
    the common "-1 means error" sentinel reads as MORE human than any real text."""
    import untell.scripts.score as sc

    monkeypatch.setattr(sc, "load_detectors", _fake_detectors([85.0]))
    r = sc.score_text("some sample text here", tier="lite")
    assert r["max"] == 1.0
    assert r["ai_percent"] == 100.0  # not 8500.0
    assert r["out_of_range_detectors"] == ["d0"]  # the adapter bug stays visible

    monkeypatch.setattr(sc, "load_detectors", _fake_detectors([-1.0]))
    r = sc.score_text("some sample text here", tier="lite")
    assert r["max"] == 0.0  # not a "more human than human" negative
    assert r["out_of_range_detectors"] == ["d0"]


def test_unscored_result_is_not_mistakable_for_a_clean_one(monkeypatch):
    """When nothing scored, max=0.0 otherwise reads as a confident "definitely human" — the most
    misleading value this function could return."""
    import untell.scripts.score as sc

    monkeypatch.setattr(sc, "load_detectors", _fake_detectors([None, None]))
    r = sc.score_text("some sample text here", tier="lite")
    assert r["scored"] is False
    assert r["flagged"] is False
    assert "warning" in r


def test_normal_scores_are_untouched(monkeypatch):
    import untell.scripts.score as sc

    monkeypatch.setattr(sc, "load_detectors", _fake_detectors([0.2, 0.9]))
    r = sc.score_text("some sample text here", tier="lite")
    assert r["max"] == 0.9
    assert r.get("scored", True) is True
    assert "out_of_range_detectors" not in r
