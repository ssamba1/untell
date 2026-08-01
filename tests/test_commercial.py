"""Commercial detector adapter tests — fully offline (HTTP mocked, env keys set per-test)."""

from __future__ import annotations

import pytest

from untell.detectors import commercial as C

_ALL_ENV = [
    "ORIGINALITY_API_KEY",
    "WINSTON_API_KEY",
    "GPTZERO_API_KEY",
    "SAPLING_API_KEY",
    "ZEROGPT_API_KEY",
    "COPYLEAKS_EMAIL",
    "COPYLEAKS_API_KEY",
]


@pytest.fixture(autouse=True)
def _clear_keys(monkeypatch):
    for v in _ALL_ENV:
        monkeypatch.delenv(v, raising=False)
    C._CL_TOKEN["token"] = None
    C._CL_TOKEN["exp"] = 0.0


def test_unavailable_without_keys():
    for det in C.commercial_detectors():
        assert det.available() is False


# (class, env var, mocked JSON response, expected AI probability in [0,1])
_CASES = [
    ("OriginalityDetector", "ORIGINALITY_API_KEY", {"score": {"ai": 0.91, "original": 0.09}}, 0.91),
    ("SaplingDetector", "SAPLING_API_KEY", {"score": 0.77}, 0.77),
    ("GPTZeroDetector", "GPTZERO_API_KEY", {"documents": [{"class_probabilities": {"ai": 0.66, "human": 0.3}}]}, 0.66),
    ("ZeroGPTDetector", "ZEROGPT_API_KEY", {"data": {"is_gpt_generated": 82}}, 0.82),
    ("WinstonDetector", "WINSTON_API_KEY", {"score": 25}, 0.75),  # 0-100 human -> AI complement
]


@pytest.mark.parametrize("cls,env,resp,expected", _CASES)
def test_detector_parses_ai_probability(monkeypatch, cls, env, resp, expected):
    monkeypatch.setenv(env, "test-key")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: resp)
    det = getattr(C, cls)()
    assert det.available() is True
    assert abs(det.score("a paragraph of text to classify") - expected) < 1e-6


def test_gptzero_falls_back_to_completely_generated_prob(monkeypatch):
    monkeypatch.setenv("GPTZERO_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"documents": [{"completely_generated_prob": 0.42}]})
    assert abs(C.GPTZeroDetector().score("text") - 0.42) < 1e-6


def test_copyleaks_logs_in_then_detects(monkeypatch):
    monkeypatch.setenv("COPYLEAKS_EMAIL", "me@example.com")
    monkeypatch.setenv("COPYLEAKS_API_KEY", "k")
    seen = []

    def fake(url, headers, body, timeout=45.0):
        seen.append(url)
        if "login" in url:
            return {"access_token": "TOKEN123"}
        return {"summary": {"ai": 0.88, "human": 0.12}}

    monkeypatch.setattr(C, "_post_json", fake)
    s = C.CopyleaksDetector().score("a sufficiently long piece of text to scan for ai content")
    assert abs(s - 0.88) < 1e-6
    assert any("login" in u for u in seen)
    assert any("writer-detector" in u for u in seen)


def test_copyleaks_token_is_cached(monkeypatch):
    monkeypatch.setenv("COPYLEAKS_EMAIL", "me@example.com")
    monkeypatch.setenv("COPYLEAKS_API_KEY", "k")
    logins = []

    def fake(url, headers, body, timeout=45.0):
        if "login" in url:
            logins.append(url)
            return {"access_token": "T"}
        return {"summary": {"ai": 0.5}}

    monkeypatch.setattr(C, "_post_json", fake)
    det = C.CopyleaksDetector()
    det.score("text one here is long enough")
    det.score("text two here is also long enough")
    assert len(logins) == 1  # token reused, not re-fetched


def test_empty_text_is_neutral(monkeypatch):
    """Empty text must return None (excluded from ensemble), not a fake 0.5 that inflates the max."""
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"score": 0.9})
    assert C.SaplingDetector().score("   ") is None


def test_gptzero_returns_none_when_no_score_field_present(monkeypatch):
    """A fabricated 0.5 is worse than no score: it enters the ensemble, drives max(), and suppresses
    the all-failed guard. Same rule already applied to mage/hc3/perplexity."""
    import untell.detectors.commercial as c

    monkeypatch.setenv("GPTZERO_API_KEY", "k")
    # Neither class_probabilities.ai nor completely_generated_prob is present.
    monkeypatch.setattr(c, "_post_json",
                        lambda *a, **k: {"documents": [{"class_probabilities": {"human": 0.9}}]})
    assert c.GPTZeroDetector().score("some text") is None


def test_gptzero_still_reads_the_fallback_field(monkeypatch):
    import untell.detectors.commercial as c

    monkeypatch.setenv("GPTZERO_API_KEY", "k")
    monkeypatch.setattr(c, "_post_json",
                        lambda *a, **k: {"documents": [{"completely_generated_prob": 0.8}]})
    assert c.GPTZeroDetector().score("some text") == 0.8


def test_zerogpt_returns_none_when_field_absent(monkeypatch):
    import untell.detectors.commercial as c

    monkeypatch.setenv("ZEROGPT_API_KEY", "k")
    monkeypatch.setattr(c, "_post_json", lambda *a, **k: {"data": {"other": 1}})
    assert c.ZeroGPTDetector().score("some text") is None


def test_zerogpt_reads_a_real_percentage(monkeypatch):
    import untell.detectors.commercial as c

    monkeypatch.setenv("ZEROGPT_API_KEY", "k")
    monkeypatch.setattr(c, "_post_json", lambda *a, **k: {"data": {"is_gpt_generated": 85}})
    assert c.ZeroGPTDetector().score("some text") == 0.85
