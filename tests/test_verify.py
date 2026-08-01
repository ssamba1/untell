"""untell-verify tests — offline (commercial HTTP mocked)."""

from __future__ import annotations

import json

import pytest

from untell.detectors import commercial as C
from untell.scripts.verify import main, verify

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
def _clear(monkeypatch):
    for v in _ALL_ENV:
        monkeypatch.delenv(v, raising=False)
    C._CL_TOKEN["token"] = None
    C._CL_TOKEN["exp"] = 0.0


def test_no_checkers_configured():
    v = verify("some text")
    assert v["configured"] == []
    assert v["passes_all"] is False
    assert v["n_configured"] == 0


def test_passes_all_when_every_checker_low(monkeypatch):
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setenv("GPTZERO_API_KEY", "k")

    def fake(url, headers, body, timeout=45.0):
        if "sapling" in url:
            return {"score": 0.08}
        return {"documents": [{"class_probabilities": {"ai": 0.12}}]}  # gptzero

    monkeypatch.setattr(C, "_post_json", fake)
    v = verify("humanized text", threshold=0.30)
    assert v["n_configured"] == 2
    assert v["passes_all"] is True
    assert v["n_passing"] == 2


def test_fails_when_one_checker_high(monkeypatch):
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setenv("GPTZERO_API_KEY", "k")

    def fake(url, headers, body, timeout=45.0):
        if "sapling" in url:
            return {"score": 0.05}
        return {"documents": [{"class_probabilities": {"ai": 0.80}}]}  # gptzero still flags

    monkeypatch.setattr(C, "_post_json", fake)
    v = verify("text", threshold=0.30)
    assert v["passes_all"] is False
    assert v["n_passing"] == 1


def test_checker_error_is_a_fail(monkeypatch):
    monkeypatch.setenv("SAPLING_API_KEY", "k")

    def boom(*a, **k):
        raise RuntimeError("503 service unavailable")

    monkeypatch.setattr(C, "_post_json", boom)
    v = verify("text")
    assert v["passes_all"] is False
    assert v["results"]["sapling"]["error"]


def test_cli_exit_codes(monkeypatch, capsys):
    # no keys, default tier=full -> local ensemble runs, output shows local results
    rc = main(["some text"])
    assert rc == 1  # local ensemble flagged it
    out = capsys.readouterr().out
    assert "local:" in out
    assert "FAIL" in out

    # all-pass -> exit 0, JSON well-formed (commercial-only to isolate from local ensemble)
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"score": 0.02})
    rc = main(["--tier", "commercial", "--json", "text"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["passes_all"] is True


def test_browser_checker_score_counts(monkeypatch):
    import untell.browser_check as bc

    monkeypatch.setattr(bc.WebUIChecker, "available", lambda self: True)
    monkeypatch.setattr(bc.WebUIChecker, "check", lambda self, text, **k: 0.05)
    v = verify("text", threshold=0.30, browser=["zerogpt"])
    assert "zerogpt(web)" in v["results"]
    assert v["results"]["zerogpt(web)"]["passes"] is True
    assert v["passes_all"] is True
    assert v["n_configured"] == 1


def test_browser_checker_unavailable_is_a_fail(monkeypatch):
    import untell.browser_check as bc

    monkeypatch.setattr(bc.WebUIChecker, "available", lambda self: False)
    v = verify("text", browser=["zerogpt"])
    r = v["results"]["zerogpt(web)"]
    assert r["passes"] is False and r["error"]
    assert v["passes_all"] is False


class _FakeDet:
    def __init__(self, name, value):
        self.name, self.tier, self._v = name, "lite", value

    def available(self):
        return True

    def score(self, text):
        return self._v


def test_no_fabricated_pass_when_nothing_scored(monkeypatch):
    """verify's whole job is an honest verdict, so it is the worst place to fabricate one.

    When every local detector returns None, score_text's max is a 0.0 PLACEHOLDER — and
    `passes: 0.0 < threshold` printed a clean pass on text that was never scored."""
    import untell.detectors.commercial as cm
    import untell.scripts.score as sc
    import untell.scripts.verify as v

    monkeypatch.setattr(sc, "load_detectors", lambda tier="lite": [_FakeDet("d0", None)])
    monkeypatch.setattr(cm, "commercial_detectors", lambda: [])

    r = v.verify("some text here", threshold=0.3, tier="lite")
    row = next(val for k, val in r["results"].items() if "max" in k)
    assert row["ai"] is None
    assert row["passes"] is False
    assert "error" in row
    assert r["passes_all"] is False


def test_real_scores_still_produce_a_verdict(monkeypatch):
    import untell.detectors.commercial as cm
    import untell.scripts.score as sc
    import untell.scripts.verify as v

    monkeypatch.setattr(sc, "load_detectors", lambda tier="lite": [_FakeDet("d0", 0.1)])
    monkeypatch.setattr(cm, "commercial_detectors", lambda: [])

    r = v.verify("some text here", threshold=0.3, tier="lite")
    row = next(val for k, val in r["results"].items() if "max" in k)
    assert row["ai"] == 0.1
    assert row["passes"] is True


def test_diagnostic_sidecar_keys_are_not_reported_as_checkers(monkeypatch):
    """score_text records "<name>__out_of_range" / "<name>__error" alongside real scores. Those are
    metadata about a detector, not detectors — a float sidecar must not become its own checker row."""
    import untell.detectors.commercial as cm
    import untell.scripts.score as sc
    import untell.scripts.verify as v

    monkeypatch.setattr(sc, "load_detectors", lambda tier="lite": [_FakeDet("d0", 85.0)])
    monkeypatch.setattr(cm, "commercial_detectors", lambda: [])

    r = v.verify("some text here", threshold=0.3, tier="lite")
    assert not any("__" in k for k in r["results"]), r["results"].keys()
