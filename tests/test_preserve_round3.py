"""Wave 3, slice 2, Track 1: preserve-lock round 3 — new fact classes still free.

Each test pins a partial lock or an unprotected fact observed in real lock()
output (see goals/results/20260815_204928-2.md). NER-safe: assertions check
that the FACT lands inside one sentinel, not exact sentinel counts, because
en_core_web_sm may add entity spans that merge with the regex locks.
"""
import pytest

from untell.scripts.preserve import lock, restore


def _whole(text: str, fact: str):
    masked, mapping = lock(text)
    assert any(fact in v for v in mapping.values()), f"{fact!r} not whole in {mapping}"
    return masked, mapping


class TestIso8601DatetimesLockWhole:
    """'2024-03-15T10:30:00Z' masked to '⟦HZ0000⟧-15T10:⟦HZ0001⟧:00Z' — the ISO
    date branch demands a word boundary after the day, 'T' breaks it, and the
    range rule then claims '2024-03' while the time fragments. The T and the
    timezone designator are the load-bearing parts, and both were free."""

    def test_iso_datetime_with_z(self):
        _whole("Sent at 2024-03-15T10:30:00Z.", "2024-03-15T10:30:00Z")

    def test_iso_datetime_with_offset(self):
        _whole("Sent at 2024-03-15T10:30:00+02:00.", "2024-03-15T10:30:00+02:00")

    def test_iso_datetime_space_separator(self):
        _whole("Logged 2024-03-15 10:30:00 local.", "2024-03-15 10:30:00")

    def test_iso_date_still_locks_whole(self):
        _whole("The date is 2024-03-15.", "2024-03-15")


class TestOrdinalOfDateCarriesTheYear:
    """'15th of March 2024' masked to '⟦HZ0000⟧ ⟦HZ0001⟧' — the 'of' branch stops
    at the month name and the year is a second, severable span, so a rewrite
    could reorder them."""

    def test_of_date_with_year(self):
        _whole("The launch was 15th of March 2024.", "15th of March 2024")

    def test_of_date_with_comma_year(self):
        _whole("The launch was 15th of March, 2024.", "15th of March, 2024")


class TestEraMarkersLockWithTheYear:
    """'753 BC' masked to '⟦HZ0000⟧ ⟦HZ0001⟧' — the year locked and the era
    marker free, so a rewrite could turn BC into AD with every sentinel intact.
    'AD 2024' locked whole only by an accident of the identifier rule; '2024 CE'
    locked nothing at all."""

    def test_bc_after_year(self):
        _whole("Rome was founded in 753 BC.", "753 BC")

    def test_bc_two_digit_year(self):
        _whole("Events in 44 BC are recorded.", "44 BC")

    def test_bce_after_year(self):
        _whole("The find dates to 4 BCE.", "4 BCE")

    def test_ad_before_year(self):
        _whole("The temple dates from AD 2024.", "AD 2024")

    def test_ce_after_year(self):
        _whole("The coin is from 2024 CE.", "2024 CE")

    def test_ce_before_year(self):
        _whole("The structure was raised CE 800.", "CE 800")


class TestCenturyOrdinalsLockWhole:
    """'The 21st century began.' masked to 'The ⟦HZ0000⟧ century began.' — the
    ordinal locked, the unit of time free, so '21st century' could become
    '21st millennium'. The '5 mg' worst case with a time unit."""

    def test_century(self):
        _whole("The 21st century began.", "21st century")

    def test_century_19th(self):
        _whole("The 19th century ended.", "19th century")

    def test_century_hyphenated(self):
        _whole("A 20th-century invention.", "20th-century")

    def test_century_with_era(self):
        _whole("In the 5th century BC.", "5th century BC")


class TestCurrencyCodesLockWithTheAmount:
    """'US$12' masked to 'US⟦HZ0000⟧' — the denomination code free, so a rewrite
    could re-denominate the price while the sentinel survives intact."""

    def test_usd_prefix(self):
        _whole("It cost US$12.", "US$12")

    def test_hkd_prefix(self):
        _whole("HK$80 is the fare.", "HK$80")

    def test_cad_prefix(self):
        _whole("C$45 was paid.", "C$45")

    def test_aud_prefix(self):
        _whole("AU$30 covers it.", "AU$30")

    def test_ntd_prefix(self):
        _whole("NT$500 is the price.", "NT$500")


class TestCurrencySymbolsBeyondDollarSign:
    """'¥1,200' masked to '¥⟦HZ0000⟧' — the yen sign is not in the currency
    class at all, so the sign itself (which carries the denomination) is free."""

    def test_yen(self):
        _whole("It cost ¥1,200.", "¥1,200")

    def test_rupee(self):
        _whole("It cost ₹500.", "₹500")

    def test_won(self):
        _whole("The fee is ₩12,000.", "₩12,000")

    def test_ruble(self):
        _whole("It cost ₽4,000.", "₽4,000")


class TestCurrencyMagnitudesLockWhole:
    """'€5.5bn' masked to '⟦HZ0000⟧bn' — the currency amount locked and the
    magnitude word free, so '€5.5bn' could become '€5.5m', three orders of
    magnitude, with every sentinel intact."""

    def test_eur_bn(self):
        _whole("The deal was €5.5bn.", "€5.5bn")

    def test_usd_bn(self):
        _whole("The deal was $5.5bn.", "$5.5bn")

    def test_gbp_m(self):
        _whole("It is worth £5m.", "£5m")

    def test_usd_trillion(self):
        _whole("It was $3.2 trillion.", "$3.2 trillion")

    def test_usd_k(self):
        _whole("It was $2k.", "$2k")


class TestLeadingPlusIsInsideTheLock:
    """'+5%' masked to '+⟦HZ0000⟧' — the sign class is [-−] and a leading plus is
    not in it, so a rewrite could flip +5% to -5% while the sentinel survives
    intact. Same shape as the documented 'LEADING ± was still free' fix."""

    def test_plus_percent(self):
        _whole("The change was +5%.", "+5%")

    def test_plus_integer(self):
        _whole("The reading was +15.", "+15")

    def test_plus_decimal(self):
        _whole("It rose +0.5 points.", "+0.5")

    def test_plus_temperature(self):
        _whole("It is +40°C outside.", "+40°C")

    def test_plus_over_minus_percent(self):
        _whole("+/-5% of samples failed.", "+/-5%")


class TestScientificNotationCarriesItsUnit:
    """'1.2e-3 m' masked to '⟦HZ0000⟧ m' — the unit free, so the exponent's unit
    could change magnitude. The tight form '1.2e-3m' was worse: the mantissa
    '1.2e' stayed free and '-3m' locked as a unit number."""

    def test_sci_spaced_unit(self):
        _whole("The cross section is 1.2e-3 m.", "1.2e-3 m")

    def test_sci_tight_unit(self):
        _whole("The cross section is 1.2e-3m.", "1.2e-3m")

    def test_sci_superscript_unit(self):
        _whole("The value is 1.2 × 10⁻³ m.", "1.2 × 10⁻³ m")

    def test_sci_joule_seconds(self):
        # The FIRST unit rides inside the lock ("6.626e-34 J s" locks "6.626e-34 J"
        # and leaves the compound " s" free — the spaced two-unit form remains a
        # documented residual, one unit past the fix's scope).
        _whole("It is 6.626e-34 J.", "6.626e-34 J")


class TestCoordinatesLockWhole:
    """'37.7749° N' masked to '⟦HZ0000⟧ N' — the hemisphere letter free, so a
    rewrite could flip N to S and move the point to the other side of the
    equator with every sentinel intact. The tight form left the degree sign
    outside too, and DMS minutes/seconds were entirely unprotected."""

    def test_decimal_degrees_with_hemisphere(self):
        _whole("37.7749° N, 122.4194° W", "37.7749° N")
        _whole("37.7749° N, 122.4194° W", "122.4194° W")

    def test_tight_degrees_with_hemisphere(self):
        _whole("37.7749°N 122.4194°W", "37.7749°N")
        _whole("37.7749°N 122.4194°W", "122.4194°W")

    def test_single_degree_with_hemisphere(self):
        _whole("The position is 51.5° N.", "51.5° N")

    def test_dms_with_hemisphere(self):
        _whole("51°30′N 0°7′W", "51°30′N")
        _whole("51°30′N 0°7′W", "0°7′W")

    def test_dms_with_seconds(self):
        _whole("51°30′12″N is the point.", "51°30′12″N")

    def test_spelled_out_hemisphere(self):
        _whole("The ship was at 45° south.", "45° south")


class TestIpPortLocksWhole:
    """'192.168.1.24:8080' masked to '⟦HZ0000⟧:⟦HZ0001⟧' — the colon free, so a
    rewrite could detach the port from the address or merge it into prose."""

    def test_ipv4_with_port(self):
        _whole("The host 192.168.1.24:8080 is up.", "192.168.1.24:8080")

    def test_ipv4_without_port_still_locks(self):
        _whole("The host 192.168.1.24 is up.", "192.168.1.24")


class TestPep440PrereleaseVersionsLockWhole:
    """'Python 3.12.0rc1' masked to '⟦HZ0000⟧.0rc1' — the version rule demands a
    '-' or '+' separator before a pre-release tag, but PEP 440 also allows the
    hyphenless forms (a1, b2, rc1, dev1), so the release segment stayed free."""

    def test_rc(self):
        _whole("Python 3.12.0rc1 was released.", "3.12.0rc1")

    def test_alpha(self):
        _whole("Needs 1.0.0a1.", "1.0.0a1")

    def test_beta(self):
        _whole("Uses 2.0b2.", "2.0b2")

    def test_dev(self):
        _whole("Built from 3.12.0.dev1.", "3.12.0.dev1")


class TestSubscriptedChemicalFormulasLock:
    """'CO₂ levels rose.' locked NOTHING — subscript digits (U+2080-2089) are not
    \\d, so the identifier rule's digit requirement never fires, and the whole
    formula is free for the rewriter. Superscript-charged ions too."""

    def test_co2_subscript(self):
        _whole("CO₂ levels rose.", "CO₂")

    def test_h2o_subscript(self):
        _whole("Water is H₂O.", "H₂O")

    def test_caco3_subscript(self):
        _whole("CaCO₃ is limestone.", "CaCO₃")

    def test_sulfate_charged(self):
        _whole("SO₄²⁻ is the anion.", "SO₄²⁻")

    def test_iron_charged(self):
        _whole("Fe³⁺ ions are present.", "Fe³⁺")

    def test_ammonium(self):
        _whole("NH₄⁺ is a cation.", "NH₄⁺")

    def test_with_coefficient(self):
        _whole("2H₂O is needed.", "2H₂O")


class TestToleranceWithUnitsOnBothSides:
    """'5% ± 2%' masked to '⟦HZ0000⟧ ⟦HZ0001⟧' — the tolerance sign free, so a
    rewrite could drop it and assert an exact figure. The documented '±5%' fix
    covers a unit on one side only."""

    def test_percent_both_sides(self):
        _whole("5% ± 2% of patients.", "5% ± 2%")

    def test_unit_first_side_only(self):
        _whole("5 ± 2% of patients.", "5 ± 2%")

    def test_plain_tolerance_still_locks(self):
        _whole("The value was 12 ± 3.", "12 ± 3")


class TestTemperatureRangesLockWhole:
    """'20°C–25°C' masked to '⟦HZ0000⟧–⟦HZ0001⟧' — the range rule carries a unit
    only on the SECOND endpoint, so a range with units on both ends splits and
    the dash stays free, exactly like the documented '5–10%' fix before it."""

    def test_range_both_units(self):
        _whole("20°C–25°C is comfortable.", "20°C–25°C")

    def test_range_first_unit_only(self):
        _whole("20°C–25 is warm.", "20°C–25")

    def test_range_percent_still_locks(self):
        _whole("5–10% of patients.", "5–10%")


class TestNerEntitiesDoNotSwallowTheSentenceTerminator:
    """'Water is H2O. And CO2 rose.' locked 'H2O.' — spaCy's entity span included
    the sentence's own full stop, so the masked text lost its terminator and
    sentence splitting downstream under-counted. The regex rules all carry
    trailing lookbehinds for exactly this; NER spans had none."""

    def test_entity_keeps_the_full_stop_outside(self):
        masked, mapping = lock("Water is H2O. And CO2 rose.")
        assert ". And " in masked, masked
        assert "H2O" in set(mapping.values())

    def test_entity_at_sentence_end_keeps_terminator(self):
        masked, mapping = lock("The compound is H2O.")
        assert masked.endswith("."), masked


class TestRoundTripFidelityForSentenceInitialDates:
    """restore(*lock(t)) == t is the documented round-trip guarantee, and it
    held for every fixture in the suite — until the locked span itself opens the
    text with a lowercase month or weekday. 'march 15, 2024 was a big day.'
    restored as 'March 15, 2024 ...' — a changed document from a round trip in
    which NOTHING was rewritten, the exact failure the list-marker guard was
    written to prevent, and lock(restore(lock(t))) != lock(t): the second lock
    carries a different span text than the first."""

    @pytest.mark.parametrize(
        "text",
        [
            "march 15, 2024 was a big day.",
            "january 5th 2024 was cold.",
            "saturday is the last day.",
            "tuesday, july 9 2024, we shipped.",
        ],
    )
    def test_round_trip_preserves_sentence_initial_dates(self, text):
        masked, mapping = lock(text)
        restored = restore(masked, mapping)
        assert restored == text, f"restore changed {text!r} -> {restored!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "march 15, 2024 was a big day.",
            "saturday is the last day.",
        ],
    )
    def test_lock_is_idempotent_over_restore(self, text):
        m1, mp1 = lock(text)
        r = restore(m1, mp1)
        assert lock(r) == (m1, mp1), f"relock of {r!r} differs from first lock"
