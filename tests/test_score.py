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
