"""score.py tests — must run in lite tier with zero ML installed, emit valid JSON."""

from __future__ import annotations

import json

from humanize.scripts.score import main, score_text


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
