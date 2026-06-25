"""humanize-prove end-to-end tests — offline (rewriter + commercial HTTP mocked)."""

from __future__ import annotations

import pytest

from eval.prove import main, prove
from humanize.detectors import commercial as C

_ENV = [
    "ORIGINALITY_API_KEY",
    "WINSTON_API_KEY",
    "GPTZERO_API_KEY",
    "SAPLING_API_KEY",
    "ZEROGPT_API_KEY",
    "COPYLEAKS_EMAIL",
    "COPYLEAKS_API_KEY",
]


class _NoopRW:
    name = "noop"

    def rewrite(self, text, score_result, threshold=0.30):
        return text


@pytest.fixture(autouse=True)
def _clear(monkeypatch):
    for v in _ENV:
        monkeypatch.delenv(v, raising=False)
    C._CL_TOKEN["token"] = None
    C._CL_TOKEN["exp"] = 0.0
    import humanize.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _NoopRW())


def test_prove_no_checkers_configured():
    v = prove("some text to humanize and prove")
    assert v["passes_all"] is False  # nothing to verify against


def test_prove_passes_when_checker_low(monkeypatch):
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"score": 0.05})
    v = prove("A sufficiently long AI-sounding paragraph for the detector to chew on.", threshold=0.30, margin=0.0)
    assert v["passes_all"] is True
    assert "humanized" in v
    assert v["after"]["results"]["sapling"]["passes"] is True


def test_prove_fails_when_checker_high(monkeypatch):
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"score": 0.95})
    v = prove("text", threshold=0.30, margin=0.0, max_iters=1)
    assert v["passes_all"] is False


def test_prove_cli_exit_codes(monkeypatch, capsys):
    rc = main(["some text"])  # no keys -> non-zero
    assert rc == 1
    capsys.readouterr()  # flush the first (non-JSON) output before the JSON run
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"score": 0.02})
    rc = main(["--json", "text long enough for the checker"])
    assert rc == 0
    import json

    assert json.loads(capsys.readouterr().out)["passes_all"] is True
