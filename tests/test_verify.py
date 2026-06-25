"""humanize-verify tests — offline (commercial HTTP mocked)."""

from __future__ import annotations

import json

import pytest

from humanize.detectors import commercial as C
from humanize.scripts.verify import main, verify

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
    # no keys -> non-zero + clear message
    rc = main(["some text"])
    assert rc == 1
    assert "No commercial checkers configured" in capsys.readouterr().out

    # all-pass -> exit 0, JSON well-formed
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"score": 0.02})
    rc = main(["--json", "text"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["passes_all"] is True


def test_browser_checker_score_counts(monkeypatch):
    import humanize.browser_check as bc

    monkeypatch.setattr(bc.WebUIChecker, "available", lambda self: True)
    monkeypatch.setattr(bc.WebUIChecker, "check", lambda self, text, **k: 0.05)
    v = verify("text", threshold=0.30, browser=["zerogpt"])
    assert "zerogpt(web)" in v["results"]
    assert v["results"]["zerogpt(web)"]["passes"] is True
    assert v["passes_all"] is True
    assert v["n_configured"] == 1


def test_browser_checker_unavailable_is_a_fail(monkeypatch):
    import humanize.browser_check as bc

    monkeypatch.setattr(bc.WebUIChecker, "available", lambda self: False)
    v = verify("text", browser=["zerogpt"])
    r = v["results"]["zerogpt(web)"]
    assert r["passes"] is False and r["error"]
    assert v["passes_all"] is False
