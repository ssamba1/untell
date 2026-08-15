"""Browser checker driven OFFLINE — a stubbed Playwright standing in for the real browser.

The real-browser tests (TestSelectorFallbackAgainstARealBrowser) launch Chromium and are
correct — but Playwright's sync API runs on greenlets, and coverage.py's default tracer does
not follow a greenlet switch, so the entire body of ``WebUIChecker.check`` (70 lines) was
invisible to measurement even though the tests passed. These tests drive ``check`` with a
pure-Python stand-in for ``playwright.sync_api``: same calls, same control flow, no browser,
fully traced. The assertions pin real behaviour — the fill/click/read pipeline, the candidate
fallback loops, and the two failure modes that must raise instead of fabricate a score.
"""

from __future__ import annotations

import sys
import types

import pytest

from untell.browser_check import (
    SiteConfig,
    WebUIChecker,
    ZeroGPTChecker,
    parse_ai_percent,
)


class _FakePage:
    """Minimal stand-in for a Playwright ``Page``: records calls, fails on demand."""

    def __init__(self, raw: str = "73% AI Generated", fail_fill=(), fail_wait=()):
        self.raw = raw
        self.fail_fill = set(fail_fill)
        self.fail_wait = set(fail_wait)
        self.filled: list[str] = []
        self.evaluated: list = []
        self.waited: list[str] = []
        self.eval_result = True

    def goto(self, url, **kw):
        self.goto_url = url

    def evaluate(self, expr, arg=None):
        self.evaluated.append((expr, arg))
        return self.eval_result

    def fill(self, sel, text, timeout=1000):
        if sel in self.fail_fill:
            raise TimeoutError(f"timeout filling {sel}")
        self.filled.append((sel, text))

    def wait_for_selector(self, sel, timeout=1000):
        self.waited.append(sel)
        if sel in self.fail_wait:
            raise TimeoutError(f"timeout waiting {sel}")

    def inner_text(self, sel):
        return self.raw


class _FakeBrowser:
    def __init__(self, page: _FakePage):
        self.page = page
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, page: _FakePage):
        self._p = page

    def launch(self, headless=True):
        return _FakeBrowser(self._p)


class _FakePlaywright:
    """Context manager standing in for ``sync_playwright()``."""

    def __init__(self, page: _FakePage):
        self.chromium = _FakeChromium(page)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_playwright(monkeypatch):
    """Install a pure-Python ``playwright`` so ``check()`` runs without a browser."""

    def _install(page: _FakePage):
        fake = _FakePlaywright(page)
        fake_mod = types.ModuleType("playwright")
        fake_mod.sync_api = fake  # `from playwright.sync_api import sync_playwright`
        fake.sync_playwright = lambda: fake  # ...imports THIS callable
        monkeypatch.setitem(sys.modules, "playwright", fake_mod)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", fake)
        return page

    return _install


CFG = SiteConfig(
    name="local",
    url="https://example.test/check",
    input_selector="#in",
    result_selector="#out",
    wait_s=2,
)


class TestCheckPipelineOffline:
    def test_reads_a_real_percentage_and_closes_the_browser(self, fake_playwright):
        page = fake_playwright(_FakePage(raw="73% AI Generated"))
        pct = WebUIChecker(CFG).check("hello world")
        assert pct == 0.73
        assert page.filled == [("#in", "hello world")]  # textarea path fills the field
        assert page.waited == ["#out"]  # and waits on the result selector
        # The submit control is clicked via JS, and the browser is closed in `finally`.
        assert page.evaluated and "querySelectorAll" in page.evaluated[0][0]
        assert page.goto_url == CFG.url

    def test_contenteditable_sites_fill_via_js(self, fake_playwright):
        page = fake_playwright(_FakePage(raw="55% AI Generated"))
        cfg = SiteConfig(
            name="ce", url="https://example.test", input_selector="#ed",
            input_mode="contenteditable", result_selector="#out", wait_s=2,
        )
        pct = WebUIChecker(cfg).check("text")
        assert pct == 0.55
        # contenteditable mode never calls page.fill; it dispatches an InputEvent instead.
        assert page.filled == []
        assert page.evaluated and "InputEvent" in page.evaluated[0][0]

    def test_contenteditable_miss_falls_back_to_the_next_candidate(self, fake_playwright):
        page = fake_playwright(_FakePage(raw="60% AI"))
        # The fake returns False (no element found) for the JS fill attempt.
        page.eval_result = False
        cfg = SiteConfig(
            name="ce", url="https://example.test", input_selector="#one, #two",
            input_mode="contenteditable", result_selector="#out", wait_s=2,
        )
        with pytest.raises(Exception) as e:
            WebUIChecker(cfg).check("text")
        assert e.value.role == "input"
        assert e.value.selectors_tried == ["#one", "#two"]

    def test_input_selector_miss_raises_and_names_every_candidate(self, fake_playwright):
        fake_playwright(_FakePage(fail_fill=("#a", "#b")))
        cfg = SiteConfig(name="local", url="u", input_selector="#a, #b",
                         result_selector="#out", wait_s=2)
        with pytest.raises(Exception) as e:
            WebUIChecker(cfg).check("x")
        assert e.value.role == "input"
        assert e.value.selectors_tried == ["#a", "#b"]
        assert e.value.site == "local"

    def test_result_selector_miss_raises_and_names_every_candidate(self, fake_playwright):
        fake_playwright(_FakePage(fail_wait=(".gone", ".also-gone")))
        cfg = SiteConfig(name="local", url="u", input_selector="#in",
                         result_selector=".gone, .also-gone", wait_s=2)
        with pytest.raises(Exception) as e:
            WebUIChecker(cfg).check("x")
        assert e.value.role == "result"
        assert e.value.selectors_tried == [".gone", ".also-gone"]

    def test_unparseable_result_raises_not_a_fake_score(self, fake_playwright):
        fake_playwright(_FakePage(raw="Analyzing..."))
        with pytest.raises(RuntimeError) as e:
            WebUIChecker(CFG).check("x")
        assert "could not parse an AI percentage" in str(e.value)
        assert "Analyzing" in str(e.value)

    def test_wait_budget_is_shared_across_candidates(self, fake_playwright):
        """Three candidates must not get three full wait_s each: `per_selector = wait_s / n`."""
        page = fake_playwright(_FakePage(fail_fill=("#a", "#b")))
        cfg = SiteConfig(name="local", url="u", input_selector="#a, #b, #c",
                         result_selector="#out", wait_s=3)
        assert WebUIChecker(cfg).check("x") == 0.73
        assert page.filled == [("#c", "x")]


def test_available_is_true_when_playwright_is_importable(monkeypatch):
    """The other half of test_available_false_without_playwright: an installed playwright must
    report available. Stubbed so the assertion holds even on machines without playwright."""
    fake_mod = types.ModuleType("playwright")
    monkeypatch.setitem(sys.modules, "playwright", fake_mod)
    assert ZeroGPTChecker().available() is True


class TestParsePercentEdgeBranches:
    """Branches of parse_ai_percent that the main table cannot reach."""

    def test_a_label_with_no_figure_is_refused(self):
        # A label exists but there are zero percentages: the label loop breaks immediately.
        assert parse_ai_percent("AI") is None
        assert parse_ai_percent("AI Generated") is None

    def test_a_malformed_range_bound_does_not_crash(self):
        # "1.2.3" matches the digit pattern but is not a float; the range handler must catch
        # that and fall back to the (valid) lower bound rather than crash the whole parse.
        assert parse_ai_percent("AI: 10%-1.2.3%") == 0.1

    def test_a_malformed_figure_is_skipped_not_scored(self):
        # Same non-float token outside a range: skipped, and with no other figure the result
        # is a refusal — never a fabricated number.
        assert parse_ai_percent("1.2.3%") is None
