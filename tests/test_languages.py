"""The per-language registry — the architecture, tested; the catalogues, absent on purpose.

The roadmap's language item says the architecture is the contribution and the catalogues have to be
written by people who speak those languages. So these tests check routing, isolation and the
honesty of the "nobody has written one" answer. There is nothing here that asserts a Chinese or
Korean tell is real, because nothing in this repo has measured one.
"""

from __future__ import annotations

import pytest

from untell import languages

ENGLISH = "Moreover, the framework leverages a robust approach to deliver outcomes at scale."
CHINESE = "此外，该框架利用强大的方法在规模上提供成果，并且显著提高了整体效率和准确性。"
KOREAN = "또한 이 프레임워크는 강력한 접근 방식을 활용하여 대규모로 결과를 제공하며 효율성을 높입니다."
RUSSIAN = "Кроме того, эта система использует надёжный подход для достижения результатов."
MIXED = "The API returned 结果 successfully, and the framework leverages a robust approach here."


class TestScriptDetection:
    @pytest.mark.parametrize(
        "text,expected",
        [
            (ENGLISH, "Latin"),
            (CHINESE, "Han"),
            (KOREAN, "Hangul"),
            (RUSSIAN, "Cyrillic"),
            (MIXED, "Latin"),  # majority rules, so one quoted phrase does not reroute the text
            ("", "Latin"),
            ("12345 !!! ...", "Latin"),  # nothing alphabetic at all
        ],
    )
    def test_dominant_script(self, text, expected):
        assert languages.dominant_script(text) == expected

    def test_it_agrees_with_the_existing_language_gate(self):
        """`tells._language_supported` and this router must not disagree: a text called supported
        and then routed to no catalogue would be scored by nothing and reported as clean."""
        from untell.scripts.tells import _language_supported

        for text in (ENGLISH, MIXED):
            assert _language_supported(text) is True
            assert languages.catalogue_for(text) is not None
        for text in (CHINESE, KOREAN, RUSSIAN):
            assert _language_supported(text) is False
            assert languages.catalogue_for(text) is None


class TestEveryScriptRangeFires:
    """Every row in `_SCRIPT_RANGES` must match a real codepoint.

    A range that matches nothing is not dead weight, it is a lie: the router counts
    characters against these blocks, and a block nobody can ever hit makes text in that
    script fall through to the unicodedata fallback — which still names the script, so the
    defect is invisible until the fallback and the block disagree. PROBED before this
    class existed: all 12 ranges fire, including the two the common-character tests never
    touch (CJK Extension A 0x3400-0x4DBF, Hangul Jamo 0x1100-0x11FF). Now the suite pins
    it instead of a one-off probe.
    """

    @pytest.mark.parametrize(
        "script,first,last",
        [
            ("Han", 0x4E00, 0x9FFF),
            ("Han", 0x3400, 0x4DBF),   # CJK Extension A — no common character exercises this
            ("Hangul", 0xAC00, 0xD7AF),
            ("Hangul", 0x1100, 0x11FF),  # Jamo — no common character exercises this
            ("Hiragana", 0x3040, 0x309F),
            ("Katakana", 0x30A0, 0x30FF),
            ("Cyrillic", 0x0400, 0x04FF),
            ("Arabic", 0x0600, 0x06FF),
            ("Hebrew", 0x0590, 0x05FF),
            ("Devanagari", 0x0900, 0x097F),
            ("Thai", 0x0E00, 0x0E7F),
            ("Greek", 0x0370, 0x03FF),
        ],
    )
    def test_the_range_matches_a_codepoint(self, script: str, first: int, last: int):
        # The range EDGES are not letters (0x0E00 is a Thai combining mark, 0x4DBF is
        # extension-A's last slot). `dominant_script` counts alphabetic characters only,
        # so assert on the first actual letter the block contains.
        for point in range(first, last + 1):
            if chr(point).isalpha():
                assert languages.dominant_script(chr(point)) == script, (
                    f"0x{point:04X} should read as {script}"
                )
                return
        raise AssertionError(f"{script} range 0x{first:04X}-0x{last:04X} contains no letters")

    def test_a_character_just_outside_a_range_does_not_claim_it(self):
        # 0x03FF is Greek's last codepoint; 0x0400 is Cyrillic's first. The boundary must
        # not bleed: a range that claimed one extra codepoint would misroute a real script.
        assert languages.dominant_script(chr(0x03FF)) == "Greek"
        assert languages.dominant_script(chr(0x0400)) == "Cyrillic"
        assert languages.dominant_script(chr(0x4DBF)) == "Han"
        assert languages.dominant_script(chr(0x4E00)) == "Han"


class TestRouting:
    def test_english_is_registered_and_is_the_existing_catalogue(self):
        from untell.scripts.tells import score_tells

        catalogue = languages.catalogue_for(ENGLISH)
        assert catalogue is not None
        assert catalogue.code == "en"
        assert catalogue.scorer is score_tells, "English must route to the shipped catalogue"

    def test_an_unwritten_language_returns_none_rather_than_english(self):
        """The failure this prevents: running the English catalogue over Korean finds no English
        tells and reports a clean score for text nothing examined."""
        for text in (CHINESE, KOREAN, RUSSIAN):
            assert languages.catalogue_for(text) is None

    def test_registering_a_language_routes_to_it(self, monkeypatch):
        calls = []

        def fake_scorer(text: str, *, include_matches: bool = False) -> dict:
            calls.append(text)
            return {"words": 1, "tells": 0, "tells_per_100w": 0.0, "by_category": {}}

        monkeypatch.setattr(languages, "_REGISTRY", dict(languages._REGISTRY))
        languages.register("zh", fake_scorer, script="Han", label="Chinese")

        catalogue = languages.catalogue_for(CHINESE)
        assert catalogue is not None and catalogue.code == "zh"
        catalogue.scorer(CHINESE)
        assert calls == [CHINESE]
        # and English is untouched by the addition
        assert languages.catalogue_for(ENGLISH).code == "en"

    def test_registering_does_not_disturb_the_english_module(self, monkeypatch):
        """Additive by construction: adding a language must not require editing `tells.py`.

        Checked by asserting that module has no knowledge of the registry at all — if it grows an
        import of `untell.languages`, the two are coupled and "add a file, touch nothing" stops
        being true.

        The check is a fresh-interpreter probe rather than sys.modules or source text: `tells.py`
        legitimately imports `untell.languages` LAZILY (inside the unsupported-language branch, to
        name the script correctly in the caveat), so a source-text assertion like
        `"untell.languages" not in source` fails on a legitimate feature, and this test module
        imports the registry at its own top level, which pollutes sys.modules for the whole class.
        A lazy import preserves additivity — a language can be added without editing `tells.py` —
        while a module-level import would make every English-only caller pay for the registry.
        The probe asserts exactly the property that matters: importing `tells` in a cold
        interpreter must not pull the registry in.
        """
        import subprocess
        import sys
        from pathlib import Path

        repo = Path(__file__).resolve().parent.parent
        probe = (
            "import sys;"
            "from untell.scripts import tells;"
            "assert 'untell.languages' not in sys.modules, "
            "'importing untell.scripts.tells must not import the language registry'"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, cwd=repo,
        )
        assert result.returncode == 0, (
            "importing untell.scripts.tells must not import the language registry — "
            f"the English catalogue has no dependency on it: {result.stderr.strip()}"
        )


class TestRegistryHygiene:
    def test_a_language_needs_a_code(self):
        with pytest.raises(ValueError):
            languages.register("", lambda text, **kw: {})
        with pytest.raises(ValueError):
            languages.register("   ", lambda text, **kw: {})

    def test_registered_returns_a_copy(self):
        """A caller mutating the returned dict must not silently deregister a language."""
        snapshot = languages.registered()
        snapshot.clear()
        assert "en" in languages.registered()

    def test_only_english_ships(self):
        """If this fails, someone added a catalogue — which is welcome, and it needs the paired
        corpus measurement that earned every number in `tells.py`, not just a word list."""
        assert set(languages.registered()) == {"en"}, (
            "a new catalogue must arrive with its own measured precision figures; see the header "
            "of untell/scripts/tells.py for what that means"
        )
