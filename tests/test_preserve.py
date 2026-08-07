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


def test_sentinel_pattern_is_defined_once():
    """The sentinel regex guards every locked citation, number and quote.

    Four modules each carried their own copy. The `{4,}` is load-bearing — lock() numbers sentinels
    with `f"⟦HZ{i:04d}⟧"`, which overflows to five digits past 9999 spans, so a copy written `\\d{4}`
    would stop matching exactly the documents with the most to lose and drop those spans on restore.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    # Every shipped package, not just untell/. A guard scoped to where the bug was last found is
    # how the next instance survives — measured three times this session, most recently when the
    # device_map guard looked only at detectors/ while a rewriter had it the whole time.
    literal = re.compile(
        r"re\.compile\(\s*r?[\"']\\u27e6HZ|re\.compile\(\s*r?[\"']⟦HZ"
        r"|re\.(?:findall|search|sub|match)\(\s*r?[\"']\\u27e6HZ|re\.(?:findall|search|sub|match)\(\s*r?[\"']⟦HZ"
    )
    offenders = []
    for package in ("untell", "eval", "training", "tests"):
        for path in sorted((root / package).rglob("*.py")):
            if path.name in ("preserve.py", "test_preserve.py"):
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if literal.search(line):
                    offenders.append(f"{path.relative_to(root)}:{i}: {line.strip()}")
    assert not offenders, (
        "import SENTINEL_RE from untell.scripts.preserve instead of re-declaring it:\n  "
        + "\n  ".join(offenders)
    )


def test_every_consumer_shares_the_same_compiled_pattern():
    from untell.rewriter.mt_pivot import _SENTINEL_RE as mt
    from untell.rewriter.t5_paraphrase import _SENTINEL_RE as t5
    from untell.rewriter.targeted import _SENTINEL_RE as targeted
    from untell.scripts.preserve import SENTINEL_RE

    assert SENTINEL_RE is targeted is t5 is mt


def test_sentinel_pattern_matches_past_9999_spans():
    """Five-digit sentinels are reachable: lock() uses a minimum width, not a fixed one."""
    from untell.scripts.preserve import SENTINEL_RE

    assert SENTINEL_RE.findall("⟦HZ0000⟧ ⟦HZ9999⟧ ⟦HZ10000⟧ ⟦HZ123456⟧") == [
        "⟦HZ0000⟧", "⟦HZ9999⟧", "⟦HZ10000⟧", "⟦HZ123456⟧"
    ]


class TestFlagsAndEnvVars:
    """CLI flags and environment variables are identifiers, not prose.

    Technical writing is a plausible target for this tool, and "Pass --tier full" rewritten as "use
    the full tier" has silently deleted the instruction. Fenced code, inline code, paths and
    snake_case were already locked; these two were not.
    """

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Pass --tier full to enable the ensemble.", "--tier"),
            ("Use --best-of 3 for stronger results.", "--best-of"),
            ("Set UNTELL_ENABLE_RADAR=1 before running.", "UNTELL_ENABLE_RADAR"),
            ("The UNTELL_LITE_NO_TORCH switch disables torch.", "UNTELL_LITE_NO_TORCH"),
        ],
    )
    def test_locked(self, text, expected):
        _masked, mapping = lock(text)
        assert expected in mapping.values(), f"{expected!r} not locked in {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "The result -- surprisingly -- was good.",
            "A well-known, state-of-the-art approach.",
            "Everything went well - mostly.",
        ],
        ids=["em-dash-substitute", "hyphenated-prose", "single-hyphen"],
    )
    def test_prose_hyphens_are_not_mistaken_for_flags(self, text):
        """Only the `--x` form is matched. A single `-x` collides with hyphenated prose, and "--"
        used as an em-dash substitute must stay rewritable."""
        _masked, mapping = lock(text)
        assert not any(v.startswith("-") for v in mapping.values()), mapping

    def test_plain_acronyms_are_not_locked_by_this_rule(self):
        """The SCREAMING_SNAKE rule requires an underscore, so ordinary acronyms stay rewritable and
        are left to the entity pass. Asserted on the rule itself, since NER may lock them anyway."""
        import re as _re

        from untell.scripts.preserve import _PATTERNS

        screaming = [rx for name, rx in _PATTERNS if name == "code"][-1]
        for word in ("AI", "NASA", "IBM", "HTTP"):
            assert not _re.search(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", word), word
        assert screaming.search("UNTELL_ENABLE_RADAR")

    @pytest.mark.parametrize(
        "text",
        [
            "Pass --tier full to enable the ensemble.",
            "Set UNTELL_ENABLE_RADAR=1 before running.",
            "The result -- surprisingly -- was good.",
        ],
    )
    def test_round_trip(self, text):
        assert restore(*lock(text)) == text


class TestFactsLockedWholeNotInPieces:
    """A fact locked in pieces is not locked: whatever falls outside the sentinel stays rewritable
    while every sentinel survives, so the integrity check passes and the fact still changed."""

    def test_medical_marker_polarity_is_inside_the_lock(self):
        """CD4+ and CD4- are opposite cell populations. Locking only the stem left the sign free.

        Measured before: "CD4+" masked to "⟦HZ0000⟧+" while "CD8-" happened to mask whole — the two
        behaved differently inside one sentence.
        """
        from untell.scripts.preserve import lock

        masked, mapping = lock("The CD4+ count fell while CD8- cells rose.")
        assert set(mapping.values()) == {"CD4+", "CD8-"}
        assert "+" not in masked and "-" not in masked

    def test_meridiem_is_inside_the_lock(self):
        """"9:30 AM" locked only "9:30", so a rewrite could move a meeting twelve hours."""
        from untell.scripts.preserve import lock

        _, m = lock("The meeting starts at 9:30 AM and ends at 4:15 PM.")
        assert set(m.values()) == {"9:30 AM", "4:15 PM"}
        _, m2 = lock("It runs 8:00 a.m. to 5:00 p.m. daily.")
        assert set(m2.values()) == {"8:00 a.m.", "5:00 p.m."}

    def test_locking_pm_does_not_eat_the_sentence_terminator(self):
        r"""`[Mm]\.?` swallowed the full stop after "PM", leaving the masked text unterminated and
        breaking sentence splitting for everything downstream."""
        from untell.scripts.preserve import lock

        masked, _ = lock("The meeting starts at 9:30 AM and ends at 4:15 PM.")
        assert masked.endswith(".")

    def test_slash_dates_lock_as_one_span(self):
        """The fraction rule took "03/04" and left "/2021" as free text, severing day-month from
        year with a rewritable separator between them."""
        from untell.scripts.preserve import lock

        _, m = lock("The incident occurred on 03/04/2021 and again on 11/12/2022.")
        assert set(m.values()) == {"03/04/2021", "11/12/2022"}

    def test_bare_fractions_and_ratios_still_work(self):
        """The slash-date rule must not swallow ordinary fractions or clock ratios."""
        from untell.scripts.preserve import lock

        _, m = lock("About 2/3 of runs passed, a ratio of 3:1.")
        assert "2/3" in m.values() and "3:1" in m.values()


class TestWeekdayAbbreviationsDoNotLockOrdinaryWords:
    """The date pattern carries re.IGNORECASE and the 3-letter weekdays are ordinary English words.

    Measured before: "She **sat** on the bench", "The **sun** was bright" and "the **wed**ding" all
    locked as date facts. Over-locking is not harmless — a locked span is one the rewriter may not
    touch, so this pinned ordinary prose the loop is supposed to be free to rewrite.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "She sat on the bench and read for an hour.",
            "The sun was bright and warm all afternoon.",
            "They wed in the spring of that year.",
            "I won the match and then lost the next one.",
        ],
    )
    def test_lowercase_weekday_words_are_not_locked(self, text):
        from untell.scripts.preserve import lock

        _, mapping = lock(text)
        assert not mapping, f"over-locked {list(mapping.values())} in {text!r}"

    @pytest.mark.parametrize("text", ["The meeting is on Wed and again on Sat.", "Due Monday."])
    def test_real_weekdays_are_still_locked(self, text):
        from untell.scripts.preserve import lock

        _, mapping = lock(text)
        assert mapping, f"failed to lock a weekday in {text!r}"

    def test_full_weekday_names_stay_case_insensitive(self):
        """"sunday" is unambiguous whatever its case, unlike "sun"."""
        from untell.scripts.preserve import lock

        _, mapping = lock("it happened on sunday afternoon")
        assert "sunday" in mapping.values()


def test_restore_is_idempotent_and_a_literal_sentinel_is_neutralised():
    """Two properties the loop now leans on, made explicit.

    `untell_text` scores restored text, so `restore` runs on strings that are sometimes already
    restored (the polish and confirm paths both hand it `final`). That is only safe because:

      1. `restore` is idempotent — a second pass finds no sentinels left to replace, so it is a
         no-op rather than a second round of substitution.
      2. A literal sentinel-lookalike in the CALLER's own text cannot collide with a real one:
         `lock` masks it too, mapping it to itself, so it is inert on the way back out.

    Without (2), idempotence alone would not be enough — a lookalike surviving into `final` would
    be replaced by whatever span happened to own that number on the second pass, silently swapping
    the user's text for someone else's citation.
    """
    text = "Report ⟦HZ0000⟧ says Smith (2020) rose 47%."
    masked, mapping = lock(text)
    once = restore(masked, mapping)

    assert once == text  # round-trips despite the lookalike
    assert restore(once, mapping) == once  # idempotent
    assert mapping["⟦HZ0000⟧"] == "⟦HZ0000⟧"  # the lookalike maps to itself


class TestSoftwareIdentifiersLockWhole:
    r"""Version strings, dependency pins and file paths used to lock PARTIALLY.

    This module's own ORDER comment calls a partial lock the worst possible outcome: a sentinel
    appears, the span looks protected, and the rest stays mutable. MEASURED before the fix:

        "v1.2.3-rc4"            -> "⟦HZ0000⟧-rc4"              pre-release tag rewritable
        "untell==0.2.0"         -> "untell==⟦HZ0000⟧.0"        locked "0.2", left ".0"
        "numpy>=1.24"           -> "numpy⟦HZ0000⟧"             package name outside the lock
        "1.2.3+build.99"        -> "⟦HZ0000⟧.3+build.⟦HZ0001⟧" build metadata severed
        r"C:\Users\me\file.txt" -> r"C:\Users\me\⟦HZ0000⟧"   directory rewritable

    A version that reads as 1.2.3 and installs as something else is wrong in the way nobody catches
    by eye, and these are exactly the spans a reader copies verbatim.
    """

    @pytest.mark.parametrize(
        ("text", "span"),
        [
            ("Release v1.2.3-rc4 shipped.", "v1.2.3-rc4"),
            ("Tag v2.0.0-beta.1 landed.", "v2.0.0-beta.1"),
            ("Install untell==0.2.0 now.", "untell==0.2.0"),
            ("Requires numpy>=1.24 today.", "numpy>=1.24"),
            ("Version 1.2.3+build.99 exists.", "1.2.3+build.99"),
            (r"Path C:\Users\me\file.txt matters.", r"C:\Users\me\file.txt"),
            ("See src/main.py for details.", "src/main.py"),
        ],
    )
    def test_the_whole_span_is_one_sentinel(self, text, span):
        masked, mapping = lock(text)
        # The failure this guards is a PARTIAL lock — the span carved across sentinels with some
        # of it left mutable, as the docstring above records. It is NOT a failure for the span to
        # sit inside a WIDER single lock: everything is still protected, only rewrite freedom is
        # narrower.
        #
        # That distinction matters because it decides whether this test passes. When spaCy's NER
        # model is installed the entity pass spans "Release v1.2.3-rc4" and
        # "Path C:\\Users\\me\\file.txt" as single entities, swallowing the leading word. Asserting
        # exact equality therefore made the test pass on a clean install and fail on any machine
        # with en_core_web_sm — an unpinned configuration deciding the result, not the code.
        assert len(mapping) == 1, f"partial lock, {len(mapping)} sentinels: {masked!r}"
        locked = next(iter(mapping.values()))
        assert span in locked, f"partial lock: {span!r} not inside {locked!r} ({masked!r})"
        assert restore(masked, mapping) == text

    def test_ordinary_prose_is_not_swept_up(self):
        """Both patterns require structure prose does not have — a separator AND an extension for a
        path, an operator or a suffix for a version. MEASURED: they fire on 0 spans across the 800
        HC3 texts (400 human, 400 AI), so no rewritable prose was pinned to buy this."""
        import untell.scripts.preserve as preserve

        pats = [p for label, p in preserve._PATTERNS if label in ("version", "path")]
        for text in (
            "It costs 1.5 million and/or more, either way.",
            "He said 2020 was hard and 3.5 times worse than 2019.",
            "The ratio was 3.5 to 1 in favour of the control group.",
        ):
            for pat in pats:
                assert not pat.search(text), f"{pat.pattern} matched {text!r}"


class TestLaTeXIsLocked:
    r"""MEASURED before these patterns existed: lock() protected ZERO spans of

        r"As \citep{smith2020} shows, see Eq.~\ref{eq:main}. We use $E = mc^2$ and \cite{jones}."

    so every citation key, cross-reference and equation in a .tex file was free for the rewriter.
    That is this repo's headline promise — citations survive — failing outright for the audience
    most likely to need it, and the most-named gap in docs/humanizer-census.md (41 of the 111
    profiles that beat untell at something named the academic/LaTeX domain).
    """

    @pytest.mark.parametrize(
        "fragment",
        [
            r"\citep{smith2020}",
            r"\citet[p.~4]{lee1999}",
            r"\cite{jones}",
            r"\ref{eq:main}",
            r"\eqref{eq:2}",
            r"\Cref{sec:intro}",
            r"\autoref{fig:1}",
            r"\label{tab:results}",
            r"\bibitem{knuth1984}",
            r"\textbf{bold}",
            r"\includegraphics{plot.pdf}",
        ],
        ids=lambda f: f.strip("\\").split("{")[0][:14],
    )
    def test_command_is_locked_whole(self, fragment):
        text = f"Prose before {fragment} and prose after."
        masked, mapping = lock(text)
        assert fragment not in masked, f"{fragment} left rewritable"
        assert restore(masked, mapping) == text
        # The WHOLE command must be one sentinel — a partial lock leaves the shell rewritable,
        # which this module's ordering comment calls the worst possible outcome.
        assert fragment in mapping.values(), f"{fragment} was split across sentinels"

    @pytest.mark.parametrize(
        "math",
        [r"$E = mc^2$", r"$$\int_0^1 x\,dx$$", r"\[a^2 + b^2 = c^2\]"],
        ids=["inline", "display", "bracket"],
    )
    def test_math_is_locked_whole(self, math):
        text = f"We know {math} holds here."
        masked, mapping = lock(text)
        assert math not in masked
        assert math in mapping.values()
        assert restore(masked, mapping) == text

    def test_environment_is_locked_whole(self):
        env = r"\begin{equation}\label{eq:x} y = \alpha x \end{equation}"
        text = f"It follows: {env} as shown."
        masked, mapping = lock(text)
        assert env in mapping.values(), "the environment was not locked as one span"
        assert restore(masked, mapping) == text

    def test_a_realistic_paragraph_round_trips(self):
        text = (
            r"As \citep{smith2020} shows, see Eq.~\ref{eq:main} and Table~\ref{tab:1}. "
            r"We use $E = mc^2$ with \cite{jones}, and \textbf{47} samples."
        )
        masked, mapping = lock(text)
        assert restore(masked, mapping) == text
        for leak in (r"\citep", r"\ref{", r"\cite{", "$E"):
            assert leak not in masked, f"{leak} leaked into the rewritable text"

    def test_prose_without_latex_is_unaffected_by_these_patterns(self):
        """The LaTeX rules must not fire on ordinary prose containing a backslash-free sentence."""
        text = "Plain prose, a citation (Smith, 2020), and the number 47."
        masked, mapping = lock(text)
        assert restore(masked, mapping) == text
        assert not any(k.startswith("latex") for k in mapping)
