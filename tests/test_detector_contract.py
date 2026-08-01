"""Contract tests for the Detector protocol — the class-level guard for this repo's #1 bug.

FIVE separate adapters shipped the same defect this session: on a failure or an unexpected response
they returned a fabricated mid-score instead of None.

    mage / hc3_roberta / perplexity_burstiness   returned 0.5 on load failure
    browser_check.check()                        returned 0.5 when it could not parse a percentage
    GPTZeroDetector                              defaulted to 0.5 when both score fields were absent
    ZeroGPTDetector                              defaulted to 50 when the field was absent

Each was fixed individually. That does not stop a sixth: the rule lives in a docstring, so nothing
mechanically enforces it. These tests do.

Why a fabricated score is worse than no score: ``score_text`` EXCLUDES a detector that returns None,
but folds a number into the ensemble. A fake 0.5 therefore enters the numeric list, drives ``max()``
— the value the whole loop optimises against — and suppresses the ``all_checkers_failed`` /
``scored: False`` guards that exist to signal exactly this situation. The loop then optimises
against, and can declare a pass on, a number no detector ever produced.
"""
from __future__ import annotations

import pytest

# (module path, class name) for every adapter whose failure path we can drive without network/models.
COMMERCIAL = [
    ("GPTZeroDetector", "GPTZERO_API_KEY", {"documents": [{"class_probabilities": {"human": 0.9}}]}),
    ("GPTZeroDetector", "GPTZERO_API_KEY", {"documents": [{}]}),
    ("ZeroGPTDetector", "ZEROGPT_API_KEY", {"data": {"unexpected": 1}}),
    ("ZeroGPTDetector", "ZEROGPT_API_KEY", {"data": {}}),
]


@pytest.mark.parametrize("cls_name,env_var,response", COMMERCIAL)
def test_commercial_adapter_returns_none_on_unusable_response(monkeypatch, cls_name, env_var, response):
    """An API response missing its score field has told us NOTHING. Returning a number invents a
    verdict the user is paying for."""
    import untell.detectors.commercial as c

    monkeypatch.setenv(env_var, "test-key")
    monkeypatch.setattr(c, "_post_json", lambda *a, **k: response)

    det = getattr(c, cls_name)()
    result = det.score("some text to score here")
    assert result is None, (
        f"{cls_name} fabricated {result!r} from a response with no score field — it would enter the "
        f"ensemble, drive max(), and suppress the all-failed guard"
    )


@pytest.mark.parametrize("cls_name,env_var", [
    ("GPTZeroDetector", "GPTZERO_API_KEY"),
    ("ZeroGPTDetector", "ZEROGPT_API_KEY"),
    ("OriginalityDetector", "ORIGINALITY_API_KEY"),
    ("WinstonDetector", "WINSTON_API_KEY"),
    ("SaplingDetector", "SAPLING_API_KEY"),
])
def test_commercial_adapter_never_returns_a_number_when_the_call_fails(monkeypatch, cls_name, env_var):
    """A transport/auth failure must not be reported as a low (or any) AI score."""
    import untell.detectors.commercial as c

    monkeypatch.setenv(env_var, "test-key")

    def _boom(*a, **k):
        raise RuntimeError("network is down")

    monkeypatch.setattr(c, "_post_json", _boom)

    det = getattr(c, cls_name)()
    try:
        result = det.score("some text to score here")
    except Exception:
        return  # raising is fine — score_text catches it and EXCLUDES the detector
    assert result is None, f"{cls_name} returned {result!r} instead of None/raise on a failed call"


def test_local_detector_returns_none_for_empty_text():
    """Empty input carries no signal. Returning a number here made score_text("") report an empty
    string as AI-generated with flagged=True."""
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    det = PerplexityBurstinessDetector()
    for text in ("", "   ", "\n\t "):
        assert det.score(text) is None


def test_score_text_excludes_none_but_would_include_a_number(monkeypatch):
    """Pins WHY the contract matters, so the reason cannot drift out of the docstring.

    A detector returning None is excluded; one returning a number is folded into max(). That is the
    entire mechanism by which a fabricated 0.5 corrupts the loop."""
    import untell.scripts.score as sc

    class _D:
        def __init__(self, name, value):
            self.name, self.tier, self._v = name, "lite", value

        def available(self):
            return True

        def score(self, text):
            return self._v

    monkeypatch.setattr(sc, "load_detectors", lambda tier="lite": [_D("d0", None)])
    r = sc.score_text("some text here", tier="lite")
    assert r["scored"] is False and r["flagged"] is False  # excluded -> no verdict invented

    monkeypatch.setattr(sc, "load_detectors", lambda tier="lite": [_D("d0", 0.5)])
    r = sc.score_text("some text here", tier="lite")
    assert r["max"] == 0.5 and r["flagged"] is True  # a fabricated 0.5 WOULD have pinned the loop
