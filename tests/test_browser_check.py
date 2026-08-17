"""Browser-checker tests — offline (the percentage parser + registry; no real browser)."""

from __future__ import annotations

import builtins

import pytest

from untell.browser_check import (
    ZEROGPT,
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


def test_user_sites_honours_the_documented_legacy_alias(tmp_path, monkeypatch):
    """_user_sites' own docstring advertises HUMANIZE_BROWSER_SITES; the code never read it, so
    anyone who followed the documentation got {} and every custom checker returned None."""
    import json as _json

    from untell.browser_check import _user_sites

    cfg = tmp_path / "sites.json"
    cfg.write_text(
        _json.dumps({"mysite": {"url": "https://example.test", "input_selector": "#in",
                                "result_selector": "#out"}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("UNTELL_BROWSER_SITES", raising=False)
    monkeypatch.setenv("HUMANIZE_BROWSER_SITES", str(cfg))
    assert "mysite" in _user_sites()


def test_user_sites_prefers_the_current_variable_over_the_alias(tmp_path, monkeypatch):
    import json as _json

    from untell.browser_check import _user_sites

    current = tmp_path / "current.json"
    legacy = tmp_path / "legacy.json"
    base = {"url": "https://example.test", "input_selector": "#in", "result_selector": "#out"}
    current.write_text(_json.dumps({"current": base}), encoding="utf-8")
    legacy.write_text(_json.dumps({"legacy": base}), encoding="utf-8")
    monkeypatch.setenv("UNTELL_BROWSER_SITES", str(current))
    monkeypatch.setenv("HUMANIZE_BROWSER_SITES", str(legacy))
    assert set(_user_sites()) == {"current"}


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


class TestAutoSelector:
    """`--browser auto` resolves to the first AVAILABLE checker (issue #2).

    Pure registry logic — no network, no browser binary, so it cannot flake. The contract
    is the order: built-ins in registration order (zerogpt is the shipped one), then user
    JSON sites in file order. 'auto' with nothing configured is None, exactly like an
    unknown name, so the CLI degrades to the existing "unavailable" error row.
    """

    def test_auto_with_only_the_builtin_picks_zerogpt(self):
        assert get_browser_checker("auto").name == "zerogpt"

    def test_auto_is_case_insensitive(self):
        assert get_browser_checker("AUTO").name == "zerogpt"
        assert get_browser_checker("Auto").name == "zerogpt"

    def test_auto_resolves_to_the_same_config_as_naming_the_site(self):
        auto = get_browser_checker("auto")
        named = get_browser_checker("zerogpt")
        assert auto.config.url == named.config.url == ZEROGPT.url

    def test_auto_prefers_builtin_over_user_site_even_when_it_sorts_after(
        self, tmp_path, monkeypatch
    ):
        # 'aaa' sorts before 'zerogpt'; auto must follow REGISTRATION order, not sorted order.

        sites = tmp_path / "sites.json"
        sites.write_text(
            '{"aaa": {"url": "https://example.test", "input_selector": "#i", '
            '"result_selector": "#o"}}',
            encoding="utf-8",
        )
        monkeypatch.setenv("UNTELL_BROWSER_SITES", str(sites))
        assert "aaa" in available_browser_checkers()
        assert get_browser_checker("auto").name == "zerogpt"

    def test_auto_picks_user_sites_in_file_order_when_builtins_are_gone(
        self, tmp_path, monkeypatch
    ):
        import untell.browser_check as bc

        sites = tmp_path / "sites.json"
        sites.write_text(
            '{"zebra": {"url": "https://z.test", "input_selector": "#i", "result_selector": "#o"}, '
            '"alpha": {"url": "https://a.test", "input_selector": "#i", "result_selector": "#o"}}',
            encoding="utf-8",
        )
        monkeypatch.setenv("UNTELL_BROWSER_SITES", str(sites))
        monkeypatch.setattr(bc, "_BUILTINS", {})
        # File order wins: zebra is listed first and is picked, even though alpha sorts first.
        assert get_browser_checker("auto").name == "zebra"

    def test_auto_with_user_site_and_builtin_still_takes_the_builtin(self, tmp_path, monkeypatch):
        import untell.browser_check as bc

        sites = tmp_path / "sites.json"
        sites.write_text(
            '{"zerogpt": {"url": "https://evil.test", "input_selector": "#i", '
            '"result_selector": "#o"}}',
            encoding="utf-8",
        )
        monkeypatch.setenv("UNTELL_BROWSER_SITES", str(sites))
        # A user entry cannot shadow a built-in — auto must hand back the SHIPPED config,
        # not the JSON impostor (same precedence get_browser_checker always enforced).
        assert get_browser_checker("auto").config.url == bc.ZEROGPT.url
        assert get_browser_checker("zerogpt").config.url == bc.ZEROGPT.url

    def test_auto_with_nothing_configured_is_none(self, tmp_path, monkeypatch):
        import untell.browser_check as bc

        monkeypatch.setattr(bc, "_BUILTINS", {})
        monkeypatch.delenv("UNTELL_BROWSER_SITES", raising=False)
        monkeypatch.chdir(tmp_path)  # no ./browser_sites.json fallback in the cwd either
        assert get_browser_checker("auto") is None

    def test_auto_does_not_claim_an_unknown_name(self):
        # Only the exact 'auto' token resolves; 'automate' stays an unknown site.
        assert get_browser_checker("automate") is None
        assert get_browser_checker("") is None


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
    ("−10% AI", None),                      # unicode minus, same refusal
    # A RANGE is one reading, and its upper bound is the safe one. The dash used to be read as a
    # minus sign, which refused the upper bound and returned the LOW end — under-stating AI, the
    # single direction this parser refuses everywhere else.
    ("AI: 10%-20%", 0.20),
    ("AI: 10% - 20%", 0.20),
    ("AI: 10 – 20%", 0.20),                 # en dash, percent only on the upper bound
    ("AI-generated: 65%—80%", 0.80),        # em dash
    ("Human: 45%-55%", None),               # an inverted range is still inverted
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


# Layouts that report BOTH figures. The old parser took the first percentage and asked only whether
# the words around it mentioned humans; with both words in range that escape hatch let the HUMAN
# figure through as P(AI) - wrong in the direction that ships text believing it passed.
BOTH_FIGURE_LAYOUTS = [
    ("Human 45% / AI 55%", 0.55),
    ("AI 55% / Human 45%", 0.55),
    ("AI: 60% Human: 40%", 0.60),
    ("Human-written: 45%   AI-generated: 55%", 0.55),
    ("45% human, 55% ai", 0.55),
    ("Human 20% | AI 80%", 0.80),
]


@pytest.mark.parametrize("readout,expected", BOTH_FIGURE_LAYOUTS)
def test_both_figures_reported_reads_the_ai_one(readout, expected):
    got = parse_ai_percent(readout)
    assert got is not None and abs(got - expected) < 1e-9, f"{readout!r} -> {got!r}, want {expected}"


@pytest.mark.parametrize(
    "readout",
    ["It is available 40%", "Certainly 25% again", "Retained 30% of the detail", "Contains 15%"],
)
def test_words_containing_ai_or_real_are_not_labels(readout):
    """The label test was a bare substring check, so "available" read as an AI label and "really"
    as a human one. Either misreading silently re-points the number at the wrong class."""
    got = parse_ai_percent(readout)
    assert got is not None, f"{readout!r} was refused because a word was mistaken for a label"


@pytest.mark.parametrize("readout", ["100% Human", "0% Human", "Human: 45%", "Real: 30%",
                                     "98% Human Written", "Likely human, 20%"])
def test_human_only_readout_is_still_refused(readout):
    """A human-labelled percentage is the inverse of what the loop needs, and there is no AI figure
    to fall back to. Refusing excludes the checker; guessing hands the loop a backwards verdict."""
    assert parse_ai_percent(readout) is None


class TestSelectorCandidates:
    """A free web detector is somebody else's website, and it gets redesigned without notice.

    When that happens a single hard-coded class name turns the checker into a 45-second timeout
    that names neither the cause nor the fix. These pin the two behaviours that make a layout
    change survivable: try several selectors, and fail with a diagnostic rather than a timeout.
    """

    @pytest.mark.parametrize(
        "spec,expected",
        [
            (".a", [".a"]),
            (".a,.b", [".a", ".b"]),
            ("  .a , .b  ", [".a", ".b"]),
            ("", []),
            (",,", []),
            # CSS that legitimately contains commas must survive intact.
            (":is(.a, .b)", [":is(.a, .b)"]),
            ('[data-x="a,b"], .c', ['[data-x="a,b"]', ".c"]),
            ("div:nth-child(2), #out", ["div:nth-child(2)", "#out"]),
        ],
    )
    def test_split_selectors(self, spec, expected):
        from untell.browser_check import _split_selectors

        assert _split_selectors(spec) == expected

    def test_site_config_exposes_candidate_lists(self):
        from untell.browser_check import SiteConfig

        c = SiteConfig(name="x", url="u", input_selector="#a, #b", result_selector=".p, .q")
        assert c.input_selectors() == ["#a", "#b"]
        assert c.result_selectors() == [".p", ".q"]

    def test_selector_miss_names_what_it_tried(self):
        from untell.browser_check import SelectorMiss

        e = SelectorMiss("zerogpt", "result", [".percentage-div", ".score"], "https://x/")
        assert e.selectors_tried == [".percentage-div", ".score"]
        assert e.role == "result"
        # The operator needs the fix, not just the failure.
        assert "--sites" in str(e) and ".percentage-div" in str(e)
        assert isinstance(e, RuntimeError)  # callers catching RuntimeError still work


@pytest.fixture(scope="module")
def _chromium_page(tmp_path_factory):
    """A local page standing in for a redesigned detector site, or skip if chromium is absent."""
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception as exc:  # browser binaries not downloaded in this environment
        pytest.skip(f"chromium unavailable: {str(exc)[:60]}")
    html = (
        "<html><body><textarea id='newTextArea'></textarea>"
        "<button onclick=\"document.getElementById('out').innerText='73% AI Generated'\">"
        "Detect</button><div id='out'></div></body></html>"
    )
    f = tmp_path_factory.mktemp("site") / "p.html"
    f.write_text(html, encoding="utf-8")
    return f.as_uri()


class TestSelectorFallbackAgainstARealBrowser:
    """Driven against a local file, so it exercises the real Playwright path with no network."""

    def test_falls_back_to_a_later_candidate(self, _chromium_page):
        from untell.browser_check import SiteConfig, WebUIChecker

        # The first candidate of each pair is the stale one.
        cfg = SiteConfig(
            name="local",
            url=_chromium_page,
            input_selector="#textArea, #newTextArea",
            result_selector=".percentage-div, #out",
            wait_s=10,
        )
        assert WebUIChecker(cfg).check("hello world", headless=True) == 0.73

    def test_missing_input_raises_selector_miss(self, _chromium_page):
        from untell.browser_check import SelectorMiss, SiteConfig, WebUIChecker

        cfg = SiteConfig(
            name="local", url=_chromium_page, input_selector="#nope", result_selector="#out",
            wait_s=6,
        )
        with pytest.raises(SelectorMiss) as e:
            WebUIChecker(cfg).check("x", headless=True)
        assert e.value.role == "input"

    def test_missing_result_raises_selector_miss(self, _chromium_page):
        from untell.browser_check import SelectorMiss, SiteConfig, WebUIChecker

        cfg = SiteConfig(
            name="local", url=_chromium_page, input_selector="#newTextArea",
            result_selector=".gone, .also-gone", wait_s=6,
        )
        with pytest.raises(SelectorMiss) as e:
            WebUIChecker(cfg).check("x", headless=True)
        assert e.value.role == "result"
        assert e.value.selectors_tried == [".gone", ".also-gone"]
