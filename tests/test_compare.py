"""Tests for the humanizer technique-comparison harness."""

from __future__ import annotations

import eval.compare_humanizers as C
from eval.compare_humanizers import _read_corpus, _render, compare


def test_read_corpus_splits_on_blank_lines(tmp_path):
    p = tmp_path / "c.txt"
    p.write_text("para one here.\n\npara two here.\n\n\npara three.", encoding="utf-8")
    assert _read_corpus(str(p)) == ["para one here.", "para two here.", "para three."]


def test_render_handles_metrics_and_errors():
    r = {
        "n": 2,
        "tier": "lite",
        "threshold": 0.3,
        "techniques": {
            "none (raw AI)": {
                "ai_max_mean": 0.5,
                "tells_per_100w_mean": 12.0,
                "tells_total": 6,
                "sim_mean": 1.0,
                "flagged_rate": 1.0,
            },
            "back_translation": {"error": "RuntimeError: no marian"},
        },
    }
    out = _render(r)
    assert "none (raw AI)" in out
    assert "skipped" in out and "no marian" in out


def test_compare_aggregates_with_stub_techniques(monkeypatch):
    # Stub the technique set so the test is fast and deterministic (no models, no network).
    def fake_techniques(tier, threshold):
        return {
            "none (raw AI)": lambda t: t,
            "strip_vocab": lambda t: t.replace("leverage", "use").replace("Furthermore, ", ""),
        }

    monkeypatch.setattr(C, "_techniques", fake_techniques)
    # Also stub score_text so we don't load detector models in a unit test.
    monkeypatch.setattr(C, "score_text", lambda text, tier="full": {"max": 0.4 if "leverage" in text else 0.1})

    texts = ["Furthermore, we leverage robust tools. Moreover, studies show it is pivotal and seamless."]
    r = compare(texts, tier="lite", threshold=0.3)
    assert r["n"] == 1
    t = r["techniques"]
    assert set(t) == {"none (raw AI)", "strip_vocab"}
    # raw keeps similarity 1.0 by construction; stripped vocab lowers the AI score and the tells.
    assert t["none (raw AI)"]["sim_mean"] == 1.0
    assert t["strip_vocab"]["ai_max_mean"] <= t["none (raw AI)"]["ai_max_mean"]
    assert t["strip_vocab"]["tells_per_100w_mean"] <= t["none (raw AI)"]["tells_per_100w_mean"]


def test_compare_empty_corpus_does_not_divide_by_zero():
    r = compare([], tier="lite")
    assert r["n"] == 0
    assert r["techniques"] == {}


def test_compare_records_error_for_failing_technique(monkeypatch):
    def boom_techniques(tier, threshold):
        def boom(t):
            raise RuntimeError("dep missing")

        return {"none (raw AI)": lambda t: t, "boom": boom}

    monkeypatch.setattr(C, "_techniques", boom_techniques)
    monkeypatch.setattr(C, "score_text", lambda text, tier="full": {"max": 0.2})
    r = compare(["some text here"], tier="lite")
    assert "error" in r["techniques"]["boom"]
    assert "dep missing" in r["techniques"]["boom"]["error"]
