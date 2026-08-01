"""Preserve-lock round-trip tests."""

from __future__ import annotations

import json

import pytest

from untell.scripts.preserve import lock, restore
from untell.scripts.preserve import main as preserve_main


def test_cli_is_ascii_safe(capsys):
    rc = preserve_main(["Smith (2020) reported 42% across [3] cases."])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # sentinels escaped to \\u27e6 — never crash a Windows cp1252 stdout
    parsed = json.loads(out)
    assert "masked" in parsed and "mapping" in parsed
    assert parsed["mapping"]  # something was locked


def _roundtrip(text: str) -> None:
    masked, mapping = lock(text)
    assert restore(masked, mapping) == text


def test_roundtrip_plain():
    _roundtrip("A perfectly ordinary sentence with no protected spans at all.")


def test_roundtrip_numeric_citation():
    _roundtrip("The effect was robust [12] and replicated in later work [3, 4].")


def test_roundtrip_author_year():
    _roundtrip("As Smith (2020) argued, and others agreed (Lee & Park, 2019, p. 4).")


def test_roundtrip_numbers_and_units():
    _roundtrip("The sample of 1,024 subjects showed a 42% increase over 3.5 years.")


def test_roundtrip_quotes_and_url():
    _roundtrip('She said "this changes everything" and cited https://example.com/x?y=1.')


def test_citation_is_masked_and_unchanged():
    text = "The result holds [12]."
    masked, mapping = lock(text)
    assert "[12]" not in masked  # the span was replaced by a sentinel
    assert "[12]" in mapping.values()  # and preserved verbatim in the mapping
    assert restore(masked, mapping) == text


def test_numbers_preserved_through_simulated_rewrite():
    text = "We observed 95% accuracy across 5 trials."
    masked, mapping = lock(text)
    # Simulate a rewrite that reorders prose but keeps sentinels intact.
    sentinels = list(mapping.keys())
    rewritten = "Across the trials we logged strong accuracy: " + ", ".join(sentinels) + "."
    restored = restore(rewritten, mapping)
    for original in mapping.values():
        assert original in restored


def test_empty_text():
    masked, mapping = lock("")
    assert masked == ""
    assert mapping == {}
    assert restore(masked, mapping) == ""


def test_sentinel_regex_handles_5plus_digit_overflow():
    # lock() numbers sentinels f"⟦HZ{i:04d}⟧" (min width 4) -> 5 digits once a doc has >9999 locked
    # spans. restore()/find_sentinels MUST still match those, or the locked span is silently dropped.
    from untell.scripts.preserve import _SENTINEL_RE, find_sentinels

    assert _SENTINEL_RE.fullmatch("⟦HZ10000⟧")  # 5 digits
    assert _SENTINEL_RE.fullmatch("⟦HZ0007⟧")  # 4 digits still ok
    masked = "alpha ⟦HZ10000⟧ omega ⟦HZ12345⟧ end"
    assert find_sentinels(masked) == {"⟦HZ10000⟧", "⟦HZ12345⟧"}
    assert restore(masked, {"⟦HZ10000⟧": "A", "⟦HZ12345⟧": "B"}) == "alpha A omega B end"


def test_roundtrip_input_containing_literal_5digit_sentinel():
    # A literal 5-digit sentinel already in the INPUT must be locked and survive verbatim.
    _roundtrip("Keep this exact token ⟦HZ10000⟧ intact through the rewrite.")


def test_percent_and_degree_units_are_locked_whole():
    """A trailing \b after the unit could only match when the symbol was followed by a word char,
    which never happens in prose. So "5%" locked NOTHING and "42%" locked only the digits."""
    from untell.scripts.preserve import lock

    for text, expected in [
        ("The error rate was 5%.", "5%"),
        ("The model achieved 42% accuracy.", "42%"),
        ("It rose to 30\u00b0.", "30\u00b0"),
        ("Temperature hit 30\u00b0C today.", "30\u00b0C"),
    ]:
        _masked, mapping = lock(text)
        assert expected in mapping.values(), f"{expected!r} not locked in {text!r}: {mapping}"


def test_percent_sign_cannot_be_rewritten_away_while_sentinel_survives():
    """The exploit the old pattern allowed: lock only the digits, leave "%" as raw text, and a
    rewrite turning "<sentinel>%" into "<sentinel> percent" passes the sentinel integrity check
    while silently changing the number's unit."""
    import re

    from untell.scripts.preserve import lock, restore

    masked, mapping = lock("The model achieved 42% accuracy.")
    sentinels = re.findall(r"\u27e6HZ\d{4,}\u27e7", masked)
    assert sentinels, "nothing was locked"
    # With the whole "42%" locked, the "%" is inside the sentinel and cannot be reached.
    assert "%" not in masked
    assert restore(masked, mapping) == "The model achieved 42% accuracy."


# --------------------------------------------------------------------------- lock COVERAGE
# The round-trip test (restore(*lock(t)) == t) cannot detect a coverage gap: unlocked text passes
# through unchanged, so the identity holds whether or not a fact is protected. That is exactly how
# "5%" shipped locked-as-nothing. These assert the OTHER property — the fact is really inside a
# sentinel — and specifically guard against PARTIAL locking, where a sentinel appears and the span
# looks protected while the rest of the fact stays mutable.
COVERAGE_CASES = [
    ("percent 1-digit", "The error rate was 5%.", "5%"),
    ("percent 2-digit", "Accuracy hit 42% overall.", "42%"),
    ("percent decimal", "It grew 3.5% last year.", "3.5%"),
    ("degree bare", "It rose to 30\u00b0.", "30\u00b0"),
    ("degree C", "Temperature hit 30\u00b0C today.", "30\u00b0C"),
    ("currency", "It cost $5 to make.", "$5"),
    ("currency large", "Revenue was $1,200,000 last year.", "$1,200,000"),
    ("decimal", "Pi is roughly 3.14 in most uses.", "3.14"),
    ("thousands", "About 1,000 people showed up.", "1,000"),
    ("year", "It launched in 2020 to acclaim.", "2020"),
    ("unit kg", "The load was 10kg total.", "10kg"),
    ("unit spaced", "We waited 5 days for it.", "5 days"),
    ("citation bracket", "Prior work showed this [12].", "[12]"),
    ("citation author", "As shown by Smith (2020), it holds.", "Smith (2020)"),
    ("url", "See https://example.com/paper for more.", "https://example.com/paper"),
    ("quote", 'She said "this is the key finding" clearly.', '"this is the key finding"'),
    ("ratio", "The split was 3:1 in favour.", "3:1"),
    ("range", "Between 10-20 people attended.", "10-20"),
    ("fraction", "About 2/3 of them agreed.", "2/3"),
    ("time", "It started at 9:30 sharp.", "9:30"),
    ("date iso", "Recorded on 2024-03-15 exactly.", "2024-03-15"),
    ("version", "Upgrade to v2.1.3 now.", "v2.1.3"),
    ("negative", "It fell by -15 points.", "-15"),
    ("scientific", "Around 1.5e10 particles.", "1.5e10"),
    ("email", "Contact a@b.com for access.", "a@b.com"),
    ("p-value", "Significant at p<0.05 level.", "p<0.05"),
]


@pytest.mark.parametrize("desc,text,must_survive", COVERAGE_CASES)
def test_fact_is_locked_whole_not_partially(desc, text, must_survive):
    from untell.scripts.preserve import lock

    _masked, mapping = lock(text)
    values = list(mapping.values())
    assert any(must_survive == v or must_survive in v for v in values), (
        f"{desc}: {must_survive!r} not locked whole in {text!r}; locked={values!r}"
    )


def test_sign_and_operator_cannot_be_stripped_from_a_locked_number():
    """The two most dangerous partial locks: a dropped minus sign flips a number's sign, and a
    freed comparison operator inverts a statistical claim ("p<0.05" -> "p>0.05")."""
    from untell.scripts.preserve import lock

    masked, _ = lock("It fell by -15 points and was significant at p<0.05 level.")
    assert "-15" not in masked  # the sign is inside the sentinel
    assert "<" not in masked  # so is the operator

# --- Fact-type coverage table -------------------------------------------------------------
# The property that matters is NOT `restore(*lock(t)) == t` (that holds whether or not a span is
# locked, because unlocked text passes through unchanged). It is: the WHOLE fact lands inside ONE
# sentinel. A partial lock is the worst outcome — a sentinel appears, so the span looks protected,
# while the rest stays freely rewritable. Measured before this table existed: 25 of 57 fact types
# locked fully, 16 partially and 16 not at all ("5 mg" locked nothing; "16 GB" locked "16" and left
# the unit loose; "March 15, 2024" locked "15" and "2024" and left the month rewritable).
FACT_CASES = [
    ("dose mg", "Patients received 5 mg daily.", "5 mg"),
    ("volume ml", "Add 250 ml of water.", "250 ml"),
    ("mass g", "The sample weighed 3 g.", "3 g"),
    ("storage GB", "The model needs 16 GB of RAM.", "16 GB"),
    ("latency ms", "Response took 250 ms.", "250 ms"),
    ("duration weeks", "The trial ran for 6 weeks.", "6 weeks"),
    ("duration months", "The trial ran for 6 months.", "6 months"),
    ("duration seconds", "It finished in 30 seconds.", "30 seconds"),
    ("distance miles", "They walked 12 miles.", "12 miles"),
    ("distance ft", "The wall is 8 ft high.", "8 ft"),
    ("speed mph", "It travels at 60 mph.", "60 mph"),
    ("temp K", "Cooled to 4 K.", "4 K"),
    ("temp C", "Heat to 37°C exactly.", "37°C"),
    ("single-digit years", "It took 3 years.", "3 years"),
    ("single-digit pct", "Growth was 5%.", "5%"),
    ("percent word", "Growth was 5 percent.", "5 percent"),
    ("US date", "Signed on March 15, 2024.", "March 15, 2024"),
    ("UK date", "Signed on 15 March 2024.", "15 March 2024"),
    ("month year", "Published in June 2023.", "June 2023"),
    ("quarter", "Revenue rose in Q3 2024.", "Q3 2024"),
    ("weekday", "The vote is on Tuesday.", "Tuesday"),
    ("ratio words", "1 in 5 patients responded.", "1 in 5"),
    ("scale", "Rated 4 out of 5 stars.", "4 out of 5"),
    ("iso date", "Signed 2024-03-15.", "2024-03-15"),
    ("negative", "The delta was -15 points.", "-15"),
    ("p value", "The result was significant (p<0.05).", "p<0.05"),
    ("n value", "The cohort had n >= 30 subjects.", "n >= 30"),
    ("range", "Ages 10-20 were included.", "10-20"),
    ("version", "Upgrade to v2.1.3 first.", "v2.1.3"),
    ("time", "The meeting starts at 9:30.", "9:30"),
    ("currency", "It cost $1,200 total.", "$1,200"),
    ("sci notation", "About 1.5e10 particles.", "1.5e10"),
    ("fraction", "Roughly 2/3 agreed.", "2/3"),
    ("plus minus", "The value was 12 +/- 3 units.", "12 +/- 3"),
    ("approx", "About ~500 users joined.", "~500"),
    ("citation brackets", "As shown [12], the effect holds.", "[12]"),
    ("citation apa", "As shown (Smith, 2020), it holds.", "(Smith, 2020)"),
    ("citation narrative", "Smith (2020) showed the effect.", "Smith (2020)"),
    ("url", "See https://example.com/a?b=1 for data.", "https://example.com/a?b=1"),
    ("doi", "See doi:10.1000/xyz123 for data.", "doi:10.1000/xyz123"),
    ("email", "Write to a.b@example.com today.", "a.b@example.com"),
    ("chem formula", "Dissolve the H2O2 sample.", "H2O2"),
    ("gene", "The BRCA1 mutation was present.", "BRCA1"),
    ("hex colour", "The color is #FF00AA here.", "#FF00AA"),
    ("section ref", "See Section 3.2 for detail.", "Section 3.2"),
    ("figure ref", "See Figure 4 for detail.", "Figure 4"),
    ("law ref", "Under 42 U.S.C. 1983 it applies.", "42 U.S.C. 1983"),
    ("file path", "Edit src/main.py now.", "src/main.py"),
    ("code call", "Call parse_json() on it.", "parse_json()"),
    ("inline code", "Run `pip install untell` first.", "`pip install untell`"),
]


@pytest.mark.parametrize("label,text,fact", FACT_CASES, ids=[c[0] for c in FACT_CASES])
def test_fact_is_locked_as_one_whole_span(label, text, fact):
    """The entire fact must sit inside a single sentinel — never split, never partly exposed."""
    masked, mapping = lock(text)
    assert restore(masked, mapping) == text
    assert any(fact in span for span in mapping.values()), (
        f"{label}: {fact!r} is not fully inside any locked span. masked={masked!r} "
        f"locked={list(mapping.values())!r}"
    )


def test_fenced_code_block_is_locked_whole():
    text = "Here is the fix:\n\n```python\nx = compute(1, 2)\n```\n\nIt works."
    masked, mapping = lock(text)
    assert restore(masked, mapping) == text
    assert any("x = compute(1, 2)" in span for span in mapping.values())


@pytest.mark.parametrize(
    "prose",
    [
        "Artificial intelligence has revolutionized numerous industries in recent years.",
        "Effective time management is essential for achieving personal and professional goals.",
        "That phrase, while memorable, obscures a good deal about how the cell actually works.",
    ],
)
def test_ordinary_prose_is_not_over_locked(prose):
    """Locking must not eat rewritable prose — a starved rewriter cannot move a detector score."""
    _masked, mapping = lock(prose)
    locked_chars = sum(len(v) for v in mapping.values())
    assert locked_chars == 0, f"over-locked {locked_chars}/{len(prose)} chars: {list(mapping.values())}"
