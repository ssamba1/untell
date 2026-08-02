"""Grammar and output-quality tests for the structural rewriter.

These tests verify that the structural rewriter produces grammatically correct,
natural-sounding output — not regex artifacts like wrong verb tense or fragments.
"""
from __future__ import annotations

import re as _re

import pytest

from untell.rewriter.structural import _flatten_participial_trailers, structural_rewrite


class TestParticipialTrailerGrammar:
    """Verify that participial trailers are converted with correct verb tense."""

    def test_underscoring_becomes_underscores(self):
        """Verb tense is asserted at the UNIT level, because a later pipeline stage legitimately
        changes the verb: "underscores" is itself AI vocabulary, so the plain-register pass swaps it
        for "shows". Asserting the exact verb survives the whole pipeline would pin an intermediate
        artifact and block that intended plainening."""
        text = "The system evolved rapidly, underscoring its importance in modern computing."
        assert "underscores its" in _flatten_participial_trailers(text)

    def test_underscoring_trailer_is_gone_after_full_pipeline(self):
        """The invariant that must survive EVERY stage: no dangling "-ing" trailer remains."""
        text = "The system evolved rapidly, underscoring its importance in modern computing."
        result = structural_rewrite(text, intensity=1.0)
        assert ", underscoring" not in result, f"trailer survived: {result}"

    def test_highlighting_becomes_highlights(self):
        text = "The data supports this view, highlighting the need for reform."
        result = structural_rewrite(text, intensity=1.0)
        assert "highlights the" in result, f"Wrong verb tense: {result}"
        assert ", highlighting" not in result

    def test_reflecting_becomes_reflects(self):
        text = "The results were positive, reflecting a broader trend."
        result = structural_rewrite(text, intensity=1.0)
        assert "reflects a" in result, f"Wrong verb tense: {result}"

    def test_multiple_trailers_all_converted(self):
        """Multiple participial trailers in one sentence: at least the first is converted."""
        text = "The model performed well, demonstrating its utility and underscoring its value."
        result = structural_rewrite(text, intensity=1.0)
        # At minimum the punctuation pattern should not leave raw fragments
        assert "demonstrates" in result or "demonstrating" not in result


class TestNegatedContrastGrammar:
    """Verify that negated contrasts produce full sentences, not fragments."""

    def test_it_is_not_produces_full_sentence(self):
        text = "It's not about the technology, it's about the people using it."
        result = structural_rewrite(text, intensity=1.0)
        # Must produce a complete sentence, not a fragment
        assert len(result) > 20
        # Must contain the positive statement
        assert "about the people" in result.lower()
        # Should NOT have awkward double-segments
        assert "about. The" not in result

    def test_not_only_but_also(self):
        text = "Not only does this improve efficiency, but it also reduces costs."
        result = structural_rewrite(text, intensity=1.0)
        assert len(result) > 10

    def test_not_just_but(self):
        text = "This is not just a tool, it is a transformative solution."
        result = structural_rewrite(text, intensity=1.0)
        assert len(result) > 10


class TestGeneralOutputQuality:
    """Verify general output quality — no artifacts, no double punctuation."""

    def test_no_double_periods(self):
        """Merged sentences must not produce '..'."""
        text = "The first sentence is here. The second sentence follows."
        result = structural_rewrite(text, intensity=1.0)
        assert ".." not in result, f"Double period found: {result}"

    def test_no_triple_spaces(self):
        """Transforms must not introduce extra whitespace."""
        text = "This is a normal sentence. It has two parts."
        result = structural_rewrite(text, intensity=1.0)
        assert "  " not in result, f"Double space found: {result}"

    def test_output_is_not_empty(self):
        assert len(structural_rewrite("Short text.", intensity=1.0)) > 0

    def test_identity_on_empty(self):
        assert structural_rewrite("", intensity=1.0) == ""

    def test_single_sentence_unchanged_structure(self):
        """A single sentence should not get merged/split (no partner)."""
        text = "This is a standalone sentence with no partner to merge with."
        result = structural_rewrite(text, intensity=1.0)
        # Length should be similar (minor changes from copula/flatten transforms)
        assert abs(len(result) - len(text)) < 20


class TestClicheRemoval:
    """Verify that common clichés and overused phrases are transformed."""

    def test_inflated_copula_flattened(self):
        text = "This solution serves as a key enabler for digital transformation."
        result = structural_rewrite(text, intensity=1.0)
        # "serves as" should be replaced with "is"
        assert "is a" in result.lower() or "serves as" not in result.lower()

    def test_vague_attribution_handled(self):
        text = "Studies show that this approach is effective in most cases."
        result = structural_rewrite(text, intensity=1.0)
        assert "evidence suggests" in result.lower() or "studies show" in result.lower()


# --- Sentence boundaries and clause merging ---------------------------------------------------
# Probing the free rewriter's actual output surfaced three defects visible to any reader:
#   "Dr. Smith published the results"  ->  "Dr, though smith published the results"
#   "Furthermore, it improves mood"    ->  ", and plus, it improves mood"
#   "Moreover, machine learning ..."   ->  ", while and, machine learning ..."
# An abbreviation split apart, a surname lowercased, and two conjunctions stacked.

ABBREVIATION_CASES = [
    ("title", "Dr. Smith published the results in 2020. The study enrolled 240 patients.", 2),
    ("country", "The U.S. economy grew steadily. Inflation fell.", 2),
    ("figure", "See Fig. 3 for detail. The trend is clear.", 2),
    ("initials", "J. R. R. Tolkien wrote it. It sold well.", 2),
    ("latin", "Use e.g. this approach instead. It works.", 2),
    ("two titles", "Prof. Jones and Mr. Lee co-authored it. They disagreed.", 2),
    ("no abbreviation", "No abbreviations here at all. Second sentence follows.", 2),
]


@pytest.mark.parametrize("label,text,expected", ABBREVIATION_CASES, ids=[c[0] for c in ABBREVIATION_CASES])
def test_abbreviations_do_not_end_a_sentence(label, text, expected):
    from untell.rewriter.structural import _split_sentences

    parts = _split_sentences(text)
    assert len(parts) == expected, f"{label}: split into {parts}"
    for abbr in ("Dr.", "U.S.", "Fig.", "Prof.", "Mr.", "e.g."):
        if abbr in text:
            assert any(abbr in p for p in parts), f"{label}: {abbr} was split apart -> {parts}"


def test_merge_never_lowercases_a_proper_noun():
    """Demoting a sentence to a subordinate clause lowercases its first word. That is right for
    "The study ..." and wrong for "Smith published ...", so a name blocks the merge instead."""
    from untell.rewriter.structural import _merge_sentences

    for _ in range(40):  # the merge is randomised; a single draw proves nothing
        out = " ".join(_merge_sentences(["The results were published.", "Smith led the team."], rate=1.0))
        assert "smith" not in out, f"proper noun lowercased: {out!r}"
        out = " ".join(_merge_sentences(["The results were published.", "NASA confirmed them."], rate=1.0))
        assert "nASA" not in out and "nasa" not in out, f"acronym mangled: {out!r}"


def test_merge_strips_a_leading_marker_instead_of_stacking_conjunctions():
    from untell.rewriter.structural import _merge_sentences

    for _ in range(40):
        out = " ".join(_merge_sentences(
            ["Regular exercise reduces risk.", "Also, it improves mood."], rate=1.0))
        low = out.lower()
        for stacked in ("and also", "but also,", "and plus", "while and", "and and", "though also"):
            assert stacked not in low, f"stacked connectives in {out!r}"


def test_merge_still_merges_ordinary_sentences():
    """The safety checks must not silently disable merging — it is the burstiness lever."""
    from untell.rewriter.structural import _merge_sentences

    merged_at_least_once = False
    for _ in range(40):
        out = _merge_sentences(["The system shuts down.", "The operator is alerted."], rate=1.0)
        if len(out) == 1:
            merged_at_least_once = True
            break
    assert merged_at_least_once, "ordinary sentences are no longer merged at all"


def test_opener_injection_keeps_an_abbreviation_capitalised():
    """Prepending an opener lowercased whatever followed, so "Dr. Smith published" became
    "In short, dr. Smith published" - the abbreviation destroyed by the transform meant to vary
    sentence rhythm. "In short, Dr. Smith published ..." is correct English; nothing needs demoting."""
    import random

    from untell.rewriter.structural import _vary_openers

    for seed in range(25):
        random.seed(seed)
        out = _vary_openers(["Dr. Smith published the results in 2020."], rate=1.0)[0]
        assert "dr." not in out, f"abbreviation lowercased: {out!r}"
        assert "Dr. Smith" in out, f"lost the name: {out!r}"


def test_merge_pair_leaves_a_proper_noun_alone():
    from untell.rewriter.structural import _merge_pair

    pair = ["The results were published.", "Smith led the team."]
    assert _merge_pair(pair, 0) == pair, "merged and lowercased a surname"
    merged = _merge_pair(["The results were published.", "The team was led well."], 0)
    assert len(merged) == 1, "ordinary sentences should still merge"


CASE_CASES = [
    ("Furthermore", "also", "Also"),
    ("furthermore", "also", "also"),
    ("FURTHERMORE", "also", "ALSO"),
    ("Moreover", "what is more", "What is more"),
    ("robust", "solid", "solid"),
    ("Delve", "dig into", "Dig into"),
]


@pytest.mark.parametrize("original,synonym,expected", CASE_CASES)
def test_substitution_carries_the_original_capitalisation(original, synonym, expected):
    """The synonym table is lower case, so substituting verbatim demoted sentence-initial words:
    "Furthermore, it improves mood" came out as "also, it improves mood"."""
    from untell.attacks.word_importance import _match_case

    assert _match_case(original, synonym) == expected


SAFE_WORD_CASES = [
    ("The", "", True), ("Organizations", "", True), ("Artificial", "", True),
    ("Machine", "", True), ("Results", "", True), ("Regular", "", True),
    ("Smith", "", False), ("Jones", "", False), ("NASA", "", False),
    ("iPhone", "", False), ("McDonald", "", False), ("Tokyo", "", False),
    # Evidence from context: a word used in lower case elsewhere is an ordinary word.
    ("Widget", "the widget was replaced twice", True),
    ("Kowalski", "the report by Kowalski was late", False),
]


@pytest.mark.parametrize("word,context,expected", SAFE_WORD_CASES)
def test_safe_to_lowercase_separates_ordinary_words_from_names(word, context, expected):
    """Merging a sentence into a clause lowercases its first word, so this decides whether a
    merge may happen at all. Too strict and the burstiness lever stops firing; too loose and
    "Smith led the team" becomes "smith led the team"."""
    from untell.rewriter.structural import _safe_to_lowercase

    assert _safe_to_lowercase(word, context) is expected, f"{word!r} in {context!r}"


# ---------------------------------------------------------------------------
# Surface well-formedness
# ---------------------------------------------------------------------------

_DOUBLE_STOP = _re.compile(r"[.!?]\s*[.!?]")


class TestNoDoubledTerminator:
    """Nothing in the pipeline looks at surface well-formedness.

    Detectors score statistics, the meaning gate checks meaning, and the tells catalogue matches
    phrases — so "…from a number of different retailers.. The list is published…" passes every
    check and ships, in output whose entire purpose is to read as human writing. Found by diffing
    punctuation between source and candidate over real rewriter output, not by reading the code.
    """

    def test_splitting_a_sentence_does_not_double_its_full_stop(self):
        from untell.rewriter.structural import _split_long_sentences

        # The second half of a split is the tail of a sentence that ALREADY ends in a full stop;
        # _split_long_sentences appended another unconditionally.
        long_sentence = (
            "The company publishes an annual ranking of the largest retailers in the United "
            "States based on sales data gathered from a great number of different retailers "
            "across the country every year."
        )
        for seed in range(20):
            import random

            random.seed(seed)
            out = " ".join(_split_long_sentences([long_sentence], max_words=10, rate=1.0))
            assert not _DOUBLE_STOP.search(out), out

    def test_conjunction_branch_does_not_double_either(self):
        from untell.rewriter.structural import _split_long_sentences

        import random

        sentence = (
            "The system collects data from many different sources every single day, and it then "
            "publishes a summary report for every registered user of the platform."
        )
        for seed in range(20):
            random.seed(seed)
            out = " ".join(_split_long_sentences([sentence], max_words=10, rate=1.0))
            assert not _DOUBLE_STOP.search(out), out

    def test_terminated_helper_is_idempotent(self):
        from untell.rewriter.structural import _terminated

        assert _terminated("ends here") == "ends here."
        assert _terminated("ends here.") == "ends here."
        assert _terminated("ends here!") == "ends here!"
        assert _terminated("ends here?") == "ends here?"
        assert _terminated('he said "stop."') == 'he said "stop."'  # closing quote after the stop
        assert _terminated("(an aside.)") == "(an aside.)"
        assert _terminated("trailing space. ") == "trailing space."
        assert _terminated("") == ""
        assert _terminated(_terminated("twice")) == "twice."


class TestDocumentLayoutSurvives:
    """A user pastes a formatted document and expects the same document back, reworded.

    The pipeline ends in `" ".join(sentences)`, so run over a whole document it returned one wall
    of text: paragraph breaks gone, three bullets merged onto one line, "1. Install it." swallowed
    into the prose as "1, and in short, and, install it.". Nothing downstream objects — the meaning
    gate compares meaning and the detectors score statistics, neither of which looks at layout.
    """

    FENCE = "```"
    CODE = "x = compute(1, 2)   # Furthermore, this is robust"

    def _doc(self):
        return (
            "# Overview\n"
            "\n"
            "Furthermore, the system leverages robust methodologies to optimize outcomes.\n"
            "\n"
            "- Furthermore, it is robust.\n"
            "- Moreover, it is seamless.\n"
            "\n"
            f"{self.FENCE}python\n"
            f"{self.CODE}\n"
            f"{self.FENCE}\n"
            "\n"
            "> Moreover, the analysis holds.\n"
            "\n"
            "1. Furthermore, install it.\n"
            "2. Moreover, configure it.\n"
        )

    def test_every_structural_element_survives(self):
        import random

        doc = self._doc()
        for seed in range(10):
            random.seed(seed)
            out = structural_rewrite(doc, intensity=1.0)
            lines = out.split("\n")
            assert lines[0] == "# Overview", out
            assert sum(1 for x in lines if x.startswith("- ")) == 2, out
            assert [x[:2] for x in lines if x[:2] in ("1.", "2.")] == ["1.", "2."], out
            assert sum(1 for x in lines if x.startswith("> ")) == 1, out
            assert out.count(self.FENCE) == 2, out
            assert doc.count("\n\n") == out.count("\n\n"), out

    def test_fenced_code_is_byte_identical(self):
        import random

        for seed in range(10):
            random.seed(seed)
            out = structural_rewrite(self._doc(), intensity=1.0)
            assert self.CODE in out, f"code was rewritten: {out}"

    def test_prose_is_still_rewritten(self):
        """Preserving layout must not turn the rewriter into a no-op."""
        import random

        random.seed(0)
        doc = self._doc()
        assert structural_rewrite(doc, intensity=1.0) != doc

    def test_paragraph_breaks_survive(self):
        import random

        src = (
            "Furthermore, the system leverages robust methodologies to optimize outcomes.\n\n"
            "Moreover, organizations increasingly utilize these tools to drive innovation."
        )
        for seed in range(10):
            random.seed(seed)
            assert "\n\n" in structural_rewrite(src, intensity=1.0)

    def test_crlf_line_endings_are_preserved(self):
        """Splitting on "\n" leaves a stray "\r" on every line; rejoining then drops it."""
        import random

        src = "Furthermore, it is robust.\r\n\r\nMoreover, it scales.\r\n"
        random.seed(0)
        out = structural_rewrite(src, intensity=1.0)
        assert "\r\n" in out
        assert "\n" not in out.replace("\r\n", "")  # no bare LF left behind

    def test_trailing_newline_is_kept(self):
        import random

        random.seed(0)
        assert structural_rewrite("Furthermore, the system is robust.\n", intensity=1.0).endswith("\n")

    def test_single_line_input_is_unaffected_by_the_layout_path(self):
        """The common case — one paragraph, no newlines — must not change behaviour."""
        import random

        src = "Furthermore, the system leverages robust methodologies to optimize outcomes."
        random.seed(3)
        out = structural_rewrite(src, intensity=1.0)
        assert "\n" not in out
        assert out != src
