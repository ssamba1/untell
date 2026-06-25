"""Browser-checker tests — offline (the percentage parser + registry; no real browser)."""

from __future__ import annotations

import builtins

import pytest

from humanize.browser_check import (
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
    monkeypatch.setenv("HUMANIZE_BROWSER_SITES", str(sites))
    assert "mysite" in available_browser_checkers()
    chk = get_browser_checker("mysite")
    assert isinstance(chk, WebUIChecker)
    assert chk.config.url == "https://example.com/d"
    assert chk.config.result_selector == ".out"


def test_malformed_user_site_is_skipped(tmp_path, monkeypatch):
    sites = tmp_path / "sites.json"
    sites.write_text('{"bad": {"no_url_field": true}, "ok": {"url": "u", "input_selector": "#i"}}', encoding="utf-8")
    monkeypatch.setenv("HUMANIZE_BROWSER_SITES", str(sites))
    names = available_browser_checkers()
    assert "ok" in names
    assert "bad" not in names  # missing required field -> skipped, not a crash


def test_available_false_without_playwright(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "playwright" or name.startswith("playwright."):
            raise ImportError("playwright not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert ZeroGPTChecker().available() is False
