"""Slice 2, Track 1: preserve-lock gaps found by mutation probes.

Each test pins a partial lock or an unprotected fact observed in real lock()
output (see goals/results/20260815_135638-2.md). NER-safe: assertions check
that the FACT lands inside one sentinel, not exact sentinel counts, because
en_core_web_sm may add entity spans that merge with the regex locks.
"""
import pytest

from untell.scripts.preserve import lock, restore

HZ = "\u27e6HZ"


class TestUrlsAndPathsKeepTheSentenceTerminator:
    """`\\S+` and `[^\\s"']+` greedily swallow the full stop that ends the
    sentence, so the masked text loses its terminator and sentence splitting
    downstream under-counts. The phone lesson fixed the same shape for a
    trailing SPACE; the URL, DOI and Windows-path branches still ate the
    trailing PERIOD."""

    def test_url_does_not_consume_the_full_stop(self):
        masked, mapping = lock("See https://example.com. Then we left.")
        assert "https://example.com" in set(mapping.values())
        assert ". Then we left." in masked, masked

    def test_url_with_query_does_not_consume_the_full_stop(self):
        masked, mapping = lock("See https://example.com/path?q=1. Then we left.")
        assert "https://example.com/path?q=1" in set(mapping.values())
        assert ". Then we left." in masked, masked

    def test_doi_does_not_consume_the_full_stop(self):
        masked, mapping = lock("See doi:10.1000/xyz. Then we left.")
        assert "doi:10.1000/xyz" in set(mapping.values())
        assert ". Then we left." in masked, masked

    def test_windows_path_does_not_consume_the_full_stop(self):
        masked, mapping = lock(r"Open C:\data\file.txt. Then we left.")
        assert r"C:\data\file.txt" in set(mapping.values())
        assert ". Then we left." in masked, masked


class TestDottedMeridiemKeepsTheSentenceTerminator:
    """'12:30 p.m. Then we left.' locked '12:30 p.m.' INCLUDING the dot that
    doubles as the sentence terminator, so the masked text was
    '⟦HZ0000⟧ Then we left.' — one sentence, no boundary. The undotted-PM fix
    was documented for '[Mm]\\.?' but the dotted form had the same hole."""

    def test_dotted_meridiem_at_sentence_end(self):
        masked, mapping = lock("We meet at 12:30 p.m. Then we left.")
        assert ". Then we left." in masked, masked
        assert any("12:30 p.m" in v for v in mapping.values())

    def test_dotted_meridiem_mid_sentence_still_absorbs_both_dots(self):
        masked, mapping = lock("We met at 4:15 p.m. and left.")
        assert any(v == "4:15 p.m." for v in mapping.values()), mapping


class TestTimeRangesLockAsOneSpan:
    """'9:30\u201310:30 AM' locked '9:30' and '10:30 AM' with the dash free (and
    '9:30-10:30' even mis-locked '-10' as a negative number), because the
    range branch sits after the time branches and never sees the gap."""

    @pytest.mark.parametrize(
        "text,fact",
        [
            ("Open 9:30\u201310:30 AM daily.", "9:30\u201310:30 AM"),
            ("From 9:30-10:30 we work.", "9:30-10:30"),
            ("Open 9:30 AM \u2013 10:30 AM daily.", "9:30 AM \u2013 10:30 AM"),
            ("From 9:30 to 10:30 we work.", "9:30 to 10:30"),
        ],
    )
    def test_time_range_is_one_sentinel(self, text, fact):
        masked, mapping = lock(text)
        assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"


class TestToleranceSignsAreInsideTheLock:
    """'\u00b15%' masked to '\u00b1\u27e6HZ0000\u27e7' — the tolerance sign free,
    so a rewrite could drop it and assert an exact figure. '~' had the same
    class fixed already; the plus-minus sign was not in the sign class."""

    @pytest.mark.parametrize(
        "text,fact",
        [
            ("The result is \u00b15%.", "\u00b15%"),
            ("Within \u00b1 2.5 \u00b0C of the target.", "\u00b1 2.5 \u00b0C"),
            ("The value was \u00b13.", "\u00b13"),
        ],
    )
    def test_plusminus_is_inside_the_sentinel(self, text, fact):
        masked, mapping = lock(text)
        assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"


class TestRangesWithUnitsLockWhole:
    """'5\u201310% of patients' locked '5\u201310' and left '%' free — the unit that
    carries the magnitude rewritable while the sentinel survives."""

    @pytest.mark.parametrize(
        "text,fact",
        [
            ("5\u201310% of patients improved.", "5\u201310%"),
            ("10-20% of the samples failed.", "10-20%"),
        ],
    )
    def test_percent_range_is_one_sentinel(self, text, fact):
        masked, mapping = lock(text)
        assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"


class TestCompoundUnitsLockWhole:
    """'10 m/s' locked '10 m' and left '/s' free; '25 m\u00b2' locked '25 m' and
    left the square free. Compound and squared units are not in the unit list,
    so a rewrite could change the speed/area while the sentinel survives."""

    @pytest.mark.parametrize(
        "text,fact",
        [
            ("The speed was 10 m/s.", "10 m/s"),
            ("The density is 5 kg/m\u00b3.", "5 kg/m\u00b3"),
            ("The area is 25 m\u00b2.", "25 m\u00b2"),
            ("Density was 2.3 g/cm\u00b3.", "2.3 g/cm\u00b3"),
            ("The noise was 50 dB.", "50 dB"),
            ("The dose was 5 \u00b5g/mL.", "5 \u00b5g/mL"),
        ],
    )
    def test_compound_unit_is_one_sentinel(self, text, fact):
        masked, mapping = lock(text)
        assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"


class TestExponentNotationLocksWhole:
    """'1.5 \u00d7 10^9' locked '1.5 \u00d7' and '10' separately, leaving the
    EXPONENT '^9' — the magnitude carrier — rewritable. Same for superscripts."""

    @pytest.mark.parametrize(
        "text,fact",
        [
            ("The count was 1.5 \u00d7 10^9 cells.", "10^9"),
            ("The count was 10\u2079 cells.", "10\u2079"),
            ("The mass is 2^31 kg.", "2^31"),
        ],
    )
    def test_caret_and_superscript_exponents(self, text, fact):
        masked, mapping = lock(text)
        assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"


class TestMonthDayWithoutYearLocksWhole:
    """'The deadline is March 15.' locked '15' and left the MONTH free — the
    exact month-name gap the date rule fixed for 'March 15, 2024', still open
    for the year-less form."""

    @pytest.mark.parametrize(
        "text,fact",
        [
            ("The deadline is March 15.", "March 15"),
            ("Christmas is December 25.", "December 25"),
            ("The vote happens on May 8.", "May 8"),
        ],
    )
    def test_month_day(self, text, fact):
        masked, mapping = lock(text)
        assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"


class TestProseMeridiemTimesLockWhole:
    """'The meeting is at 5 p.m.' locked NOTHING — a time fact fully rewritable
    (the colon-time rule does not cover the prose form)."""

    @pytest.mark.parametrize(
        "text,fact",
        [
            ("The meeting is at 5 p.m.", "5 p.m"),
            ("We start at 9 a.m. sharp.", "9 a.m"),
            ("The train leaves at 3 pm.", "3 pm"),
        ],
    )
    def test_prose_meridiem(self, text, fact):
        masked, mapping = lock(text)
        assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"
        assert masked.endswith("."), masked  # terminator survives the lock


class TestMagnitudeLetterUnitsLockWhole:
    """'The cap is 3.5M' locked NOTHING ('3.5' fails its \\b before the 'M'), and
    '5 M HCl' locked nothing either — both are facts whose letter unit carries
    the magnitude."""

    @pytest.mark.parametrize(
        "text,fact",
        [
            ("The cap is 3.5M.", "3.5M"),
            ("The solution is 5 M HCl.", "5 M"),
        ],
    )
    def test_magnitude_letter_units(self, text, fact):
        masked, mapping = lock(text)
        assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"


class TestSpacedAndParenPhoneFormats:
    """'+44 20 7946 0958' locked the digit groups SEPARATELY (and the '+' was
    free); '020 7946 0958' and '123 456 7890' similarly — a phone is
    reassemblable while every sentinel survives. E.164 also ate the sentence
    period: 'Call +1-555-123-4567. Then leave.' became 'Call \u27e6HZ0000\u27e7 Then leave.'"""

    @pytest.mark.parametrize(
        "text,fact",
        [
            ("Call +44 20 7946 0958.", "+44 20 7946 0958"),
            ("Call 020 7946 0958 today.", "020 7946 0958"),
            ("Call 123 456 7890 now.", "123 456 7890"),
            ("Call (555) 123-4567 now.", "(555) 123-4567"),
            ("Call +1 (555) 123-4567 now.", "+1 (555) 123-4567"),
        ],
    )
    def test_phone_format_is_one_sentinel(self, text, fact):
        masked, mapping = lock(text)
        assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"

    def test_e164_phone_keeps_the_sentence_terminator(self):
        masked, mapping = lock("Call +1-555-123-4567. Then leave.")
        assert "+1-555-123-4567" in set(mapping.values())
        assert ". Then leave." in masked, masked


class TestNerDoesNotLockNewlyObservedCommonWords:
    """Measured on en_core_web_sm: 'Lunch is at 12:30 p.m.' locked 'Lunch' as a
    PERSON entity, and the sentence-initial 'Insert', 'Map', 'Mode' are tagged
    PERSON too. The common-word filter missed them."""

    @pytest.mark.parametrize(
        "word,text",
        [
            ("Lunch", "Lunch is at 12:30 p.m. Then work."),
            ("Insert", "Insert the key before closing. Then test."),
            ("Map", "Map the results to the table. Then plot."),
            ("Mode", "Mode selection matters here. Then run."),
        ],
    )
    def test_common_word_not_locked(self, word, text):
        pytest.importorskip("spacy")
        pytest.importorskip("en_core_web_sm")
        masked, _ = lock(text)
        assert word in masked, f"lock() masked common word {word!r}: {masked!r}"


ROUNDTRIP_TEXTS = [
    "See https://example.com. Then we left.",
    "See https://example.com/path?q=1. Then we left.",
    "See doi:10.1000/xyz. Then we left.",
    r"Open C:\data\file.txt. Then we left.",
    "We meet at 12:30 p.m. Then we left.",
    "We met at 4:15 p.m. and left.",
    "Open 9:30\u201310:30 AM daily.",
    "From 9:30-10:30 we work.",
    "Open 9:30 AM \u2013 10:30 AM daily.",
    "From 9:30 to 10:30 we work.",
    "The result is \u00b15%.",
    "Within \u00b1 2.5 \u00b0C of the target.",
    "The value was \u00b13.",
    "5\u201310% of patients improved.",
    "The speed was 10 m/s.",
    "The density is 5 kg/m\u00b3.",
    "The area is 25 m\u00b2.",
    "Density was 2.3 g/cm\u00b3.",
    "The noise was 50 dB.",
    "The dose was 5 \u00b5g/mL.",
    "The count was 1.5 \u00d7 10^9 cells.",
    "The count was 10\u2079 cells.",
    "The mass is 2^31 kg.",
    "The deadline is March 15.",
    "Christmas is December 25.",
    "The meeting is at 5 p.m.",
    "We start at 9 a.m. sharp.",
    "The train leaves at 3 pm.",
    "The cap is 3.5M.",
    "The solution is 5 M HCl.",
    "Call +44 20 7946 0958.",
    "Call 020 7946 0958 today.",
    "Call 123 456 7890 now.",
    "Call (555) 123-4567 now.",
    "Call +1 (555) 123-4567 now.",
    "Call +1-555-123-4567. Then leave.",
]


def test_all_new_fact_texts_round_trip():
    for text in ROUNDTRIP_TEXTS:
        masked, mapping = lock(text)
        assert restore(masked, mapping) == text, f"round trip broke {text!r}"
