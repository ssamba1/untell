"""Browser-checker tests — offline (the percentage parser + registry; no real browser)."""

from __future__ import annotations

import builtins

import pytest

from untell.browser_check import (
    WebUIChecker,
    ZeroGPTChecker,
    available_browser_checkers,
    get_browser_checker,
    parse_ai_percent,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("100%AI GPT*", 1.0),  # confirmed ZeroGPT result string
        ("55% AI Generated", 0.55),
        ("Your text is 0% AI", 0.0),
        ("12.5%", 0.125),
        ("AI: 150%", 1.0),  # clamped
    ],
)
def test_parse_ai_percent(text, expected):
    assert abs(parse_ai_percent(text) - expected) < 1e-6


def test_parse_ai_percent_none_when_no_number():
    assert parse_ai_percent("no percentage here") is None
    assert parse_ai_percent("") is None
    assert parse_ai_percent(None) is None


def test_registry_builtin():
    assert "zerogpt" in available_browser_checkers()
    chk = get_browser_checker("ZeroGPT")  # case-insensitive
    assert isinstance(chk, WebUIChecker)
    assert chk.name == "zerogpt"
    assert chk.config.input_selector == "#textArea"
    assert get_browser_checker("nonexistent-site") is None


def test_zerogpt_class_still_constructs():
    z = ZeroGPTChecker()
    assert isinstance(z, WebUIChecker)
    assert z.name == "zerogpt"


def test_user_defined_site_from_json(tmp_path, monkeypatch):
    sites = tmp_path / "sites.json"
    sites.write_text(
        '{"mysite": {"url": "https://example.com/d", "input_selector": "#in", '
        '"result_selector": ".out", "submit_button_text": "scan"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("UNTELL_BROWSER_SITES", str(sites))
    assert "mysite" in available_browser_checkers()
    chk = get_browser_checker("mysite")
    assert isinstance(chk, WebUIChecker)
    assert chk.config.url == "https://example.com/d"
    assert chk.config.result_selector == ".out"


def test_malformed_user_site_is_skipped(tmp_path, monkeypatch):
    sites = tmp_path / "sites.json"
    sites.write_text('{"bad": {"no_url_field": true}, "ok": {"url": "u", "input_selector": "#i"}}', encoding="utf-8")
    monkeypatch.setenv("UNTELL_BROWSER_SITES", str(sites))
    names = available_browser_checkers()
    assert "ok" in names
    assert "bad" not in names  # missing required field -> skipped, not a crash


def test_underscore_comment_keys_are_tolerated(tmp_path, monkeypatch):
    sites = tmp_path / "sites.json"
    sites.write_text(
        '{"_comment": "a note", "site1": {"url": "u", "input_selector": "#i", "_caveat": "weak"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("UNTELL_BROWSER_SITES", str(sites))
    names = available_browser_checkers()
    assert "site1" in names  # loads despite the per-entry _caveat
    assert "_comment" not in names  # top-level comment skipped, not crash
    assert get_browser_checker("site1").config.url == "u"


def test_shipped_example_file_parses(monkeypatch):
    # The committed examples/browser_sites.example.json must load without error.
    import os.path

    p = os.path.join(os.path.dirname(__file__), "..", "examples", "browser_sites.example.json")
    if not os.path.isfile(p):
        return
    monkeypatch.setenv("UNTELL_BROWSER_SITES", p)
    names = available_browser_checkers()
    assert "decopy" in names and "detecting-ai" in names


def test_available_false_without_playwright(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "playwright" or name.startswith("playwright."):
            raise ImportError("playwright not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert ZeroGPTChecker().available() is False


def test_unparseable_result_raises_instead_of_returning_a_fake_score(monkeypatch):
    """An unparseable result is a FAILURE, not a neutral 0.5.

    wait_for_selector can return the moment a placeholder element exists in the initial DOM, before
    the real score lands. Returning 0.5 there fed a fabricated score into the loop: it entered the
    numeric list, drove max(), and suppressed the all_checkers_failed flag that exists to signal
    exactly this case — so the loop would optimise against, and declare a pass on, a score no
    detector ever produced. Same bug class already fixed in the mage/hc3/perplexity adapters.
    """
    from untell.browser_check import parse_ai_percent

    # The parser itself must report "no percentage here" rather than guessing.
    assert parse_ai_percent("Hang on while we verify your browser") is None
    assert parse_ai_percent("") is None
    assert parse_ai_percent("Analyzing...") is None


def test_browser_failure_is_excluded_from_the_ensemble_not_averaged_in(monkeypatch):
    """The loop must treat a failed checker as absent, and flag the all-failed case."""
    import untell.browser_check as bc
    import untell.scripts.run as run_mod

    class _Broken:
        def available(self):
            return True

        def check(self, text, **k):
            raise RuntimeError("could not parse an AI percentage from 'Analyzing...'")

    monkeypatch.setattr(bc, "get_browser_checker", lambda name: _Broken())
    scorer = run_mod._browser_scorer(["zerogpt"], {}, 0.30)
    out = scorer("some text")
    assert out["detectors"]["zerogpt"] is None       # excluded, not 0.5
    assert out.get("all_checkers_failed") is True    # and the failure is signalled


PARSE_CASES = [
    # (page text, expected P(AI))
    ("100% AI GPT*", 1.0),
    ("55% AI Generated", 0.55),
    ("0% AI", 0.0),
    ("AI Score: 87.5%", 0.875),
    ("  73 % ai  ", 0.73),
    ("12.345% AI", 0.12345),
    ("AI: 60% Human: 40%", 0.60),          # AI figure comes first — use it
    # Must refuse rather than guess:
    ("Human: 45%", None),                   # INVERTED — 45% human is 55% AI
    ("45% Human Written", None),
    ("150% AI", 1.0),                       # clamped — over-stating AI is safe
    ("-10% AI", None),                      # sign was silently dropped -> read as 0.10
    ("Analyzing...", None),
    ("Hang on while we verify your browser", None),
    ("", None),
]


@pytest.mark.parametrize("text,expected", PARSE_CASES)
def test_parse_ai_percent_refuses_untrustworthy_readouts(text, expected):
    """A misparse here becomes a real detector verdict the loop optimises against.

    "Human: 45%" is the dangerous one: it means 45% HUMAN (55% AI), and returning 0.45 hands the
    loop a score wrong in the direction that looks like success. "-10% AI" was read as 0.10 because
    the digit-only pattern cannot see a leading sign — the same sign-dropping bug found in the
    preserve-lock. Both now return None, so check() raises and the checker is EXCLUDED rather than
    contributing a fabricated number."""
    from untell.browser_check import parse_ai_percent

    got = parse_ai_percent(text)
    if expected is None:
        assert got is None, f"{text!r} should be refused, got {got!r}"
    else:
        assert got is not None and abs(got - expected) < 0.02, f"{text!r} -> {got!r}, want {expected}"
