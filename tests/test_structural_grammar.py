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

    def test_underscoring_flattens_straight_to_a_finite_non_tell_verb(self):
        """"underscores" is itself AI vocabulary, so this stage used to emit a tell and rely on the
        later plain-register pass to swap it for "shows".

        That pass is probabilistic — it fires with probability `intensity * profile["register"]` —
        so the cleanup was never guaranteed, and this test previously documented the workaround
        instead of the fix. _PARTICIPIAL_VERBS now maps straight to "shows" and the intermediate
        tell is never created at all.
        """
        text = "The system evolved rapidly, underscoring its importance in modern computing."
        assert "shows its" in _flatten_participial_trailers(text)

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


class TestNotOnlyKeepsBothHalves:
    """"not only X but also Y" is not a negated contrast — X and Y are BOTH asserted.

    The handler returned everything after "but also", but the match spans only
    "not only X but also" (Y and the head sit outside it), so that is the empty string: X was
    deleted and a doubled space left where it had been. Content loss from a transform whose
    documented contract is to preserve the positive statement.
    """

    @pytest.mark.parametrize(
        "text,keep",
        [
            ("It's not only faster, but also cheaper to run.", ["faster", "cheaper"]),
            (
                "The change is not only a performance win but also a cost saving.",
                ["performance win", "cost saving"],
            ),
            (
                "The tool is not only free but also open source.",
                ["free", "open source"],
            ),
        ],
    )
    def test_both_claims_survive(self, text, keep):
        from untell.rewriter.structural import _flatten_negated_contrast

        result = _flatten_negated_contrast(text)
        for phrase in keep:
            assert phrase in result, f"dropped {phrase!r}: {result!r}"

    def test_no_doubled_space_is_left_behind(self):
        from untell.rewriter.structural import _flatten_negated_contrast

        result = _flatten_negated_contrast("It's not only faster, but also cheaper to run.")
        assert "  " not in result, repr(result)

    def test_the_construction_itself_is_gone(self):
        from untell.rewriter.structural import _flatten_negated_contrast

        result = _flatten_negated_contrast("It's not only faster, but also cheaper to run.")
        assert "not only" not in result.lower()
        assert "but also" not in result.lower()


class TestMergeRespectsSentenceTerminators:
    """_merge_sentences used rstrip(".") where _merge_pair — the same merge, other copy — used
    rstrip(".!?"), so the other terminators survived and the connector landed straight after one:

        "The results were remarkable!" + "The team published them."
          -> "The results were remarkable!; the team published them."
    """

    def test_an_exclamation_does_not_survive_into_the_middle(self):
        import random

        from untell.rewriter.structural import _merge_sentences

        random.seed(0)
        out = _merge_sentences(["The results were remarkable!", "The team published them."], rate=1.0)
        joined = " ".join(out)
        assert "!;" not in joined and "!," not in joined, joined

    @pytest.mark.parametrize("merge", ["_merge_sentences", "_merge_pair"])
    def test_a_question_is_never_demoted_to_a_clause(self, merge):
        """"Was the effect real, and the replication says yes" is not English: the interrogative
        word order cannot carry a coordinate clause, and appending a period gives "?." either way.
        Both copies of the merge must decline."""
        import random

        import untell.rewriter.structural as st

        sents = ["Was the effect real?", "The replication says yes."]
        random.seed(0)
        out = (
            st._merge_sentences(list(sents), rate=1.0)
            if merge == "_merge_sentences"
            else st._merge_pair(list(sents), 0)
        )
        assert out == sents, out

    def test_ordinary_sentences_still_merge(self):
        import random

        from untell.rewriter.structural import _merge_sentences

        random.seed(0)
        out = _merge_sentences(["The results were clear.", "The team published them."], rate=1.0)
        assert len(out) == 1, out


class TestSplitNeedsARealClauseBoundary:
    """_split_one dropped the conjunction it split on, which is right for two clauses and wrong
    for two verb phrases sharing one subject:

        "The engineer opened the log at midnight and traced the fault to a stale cache entry."
          -> "The engineer opened the log at midnight." / "Traced the fault to a stale cache entry."

    The second is a subject-less fragment. There is no parser here, so the check is conservative:
    an unrecognised word after the conjunction means "don't split".
    """

    @pytest.mark.parametrize(
        "sentence",
        [
            "The committee reviewed the lengthy proposal in detail and rejected it without much debate.",
            "The engineer opened the failing service log at midnight and traced the fault to a cache entry.",
            "The analyst gathered the quarterly figures from every region and summarised them for the board.",
        ],
    )
    def test_a_shared_subject_is_not_split(self, sentence):
        from untell.rewriter.structural import _split_one

        assert _split_one(sentence) is None, _split_one(sentence)

    @pytest.mark.parametrize(
        "sentence",
        [
            "The engineer opened the failing service log at midnight and it turned out to be a cache entry.",
            "The committee reviewed the proposal for several weeks, and the board approved it in the end.",
            "The tests ran overnight on the build server and the report was waiting in the morning.",
        ],
    )
    def test_a_real_clause_boundary_still_splits(self, sentence):
        from untell.rewriter.structural import _split_one

        out = _split_one(sentence)
        assert out is not None and len(out) == 2, sentence
        assert all(part.strip() for part in out)

    def test_no_split_produces_a_verb_initial_fragment(self):
        """The property, stated directly: whatever comes back must start with something that can
        begin a clause."""
        from untell.rewriter.structural import _split_one, _starts_a_clause

        sentences = [
            "The committee reviewed the lengthy proposal in detail and rejected it without debate.",
            "The engineer opened the failing service log at midnight and traced the fault quickly.",
            "The engineer opened the failing service log at midnight and it turned out to be stale.",
            "The researcher collected the samples over three months and the lab processed them all.",
        ]
        for s in sentences:
            out = _split_one(s)
            if out:
                assert _starts_a_clause(out[1].split()[0]), f"{s!r} -> {out!r}"


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
        import random

        from untell.rewriter.structural import _split_long_sentences

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


class TestOpenersAreNotPrependedOntoOrdinaryCapitals:
    """`_vary_openers` used to prepend a connective even when it could not lowercase what followed.

    That is correct English for a name — "Actually, Smith published ..." — and visibly broken for
    an ordinary word the evidence check merely failed to confirm:

        "Actually, Issue #4821 tracks the release ..."
        "As it turns out, Run untell==0.2.0 to begin ..."

    MEASURED over 3112 sentence-initial capitals in 400 HC3 texts: 21.2% reach that branch, and
    475 of those 661 have no proper-noun evidence ("Replace", "Same", "Also", "Hence",
    "Eventually"). Broken capitalisation is itself an AI tell, so the transform meant to remove
    tells was adding one.
    """

    def _vary(self, sentences):
        import random

        from untell.rewriter.structural import _vary_openers

        random.seed(0)
        return _vary_openers(sentences, rate=1.0)  # force the transform on every sentence

    def test_an_ordinary_capitalised_word_is_left_alone(self):
        """"Issue" appears nowhere else, so nothing proves it is a name — skip rather than mangle."""
        out = self._vary(["Issue 4821 tracks the release shipped last week."])
        assert out == ["Issue 4821 tracks the release shipped last week."]

    def test_a_proper_noun_still_gets_an_opener(self):
        """Capitalised mid-sentence elsewhere is real evidence, and the capital must survive."""
        sentences = [
            "Smith published the results last spring.",
            "The Smith study was widely cited.",
        ]
        out = self._vary(sentences)
        assert out[0] != sentences[0], "a name should still be eligible for an opener"
        assert "Smith published" in out[0], f"the capital was destroyed: {out[0]!r}"

    def test_an_acronym_keeps_its_capitals(self):
        out = self._vary(["NASA confirmed the launch window this morning."])
        assert "NASA confirmed" in out[0]

    def test_a_safe_word_is_lowercased_when_an_opener_lands(self):
        sentences = ["Researchers found the effect. The researchers repeated it."]
        out = self._vary(sentences)
        if out[0] != sentences[0]:
            assert "researchers found" in out[0], out[0]


def test_an_opener_is_not_stacked_on_a_sentence_that_already_has_one():
    """Found by scanning 30 real HC3 rewrites for mechanical breakage:

        "Put simply, also, wine is often shipped and stored at specific temperatures ..."

    `_LEADING_MARKER_RE` exists to catch exactly this and was consulted only by the clause-merge
    path, so the opener transform stacked a second connective onto the first.
    """
    import random

    from untell.rewriter.structural import _vary_openers

    random.seed(1)
    already = [
        "Also, wine is shipped at specific temperatures to preserve its quality.",
        "However, salt is often the most effective option available today.",
        "Moreover, the system leverages robust methodologies across sectors.",
        "But the results did not replicate in the second cohort at all.",
    ]
    assert _vary_openers(already, rate=1.0) == already


class TestASplitNeverStrandsAConjunction:
    """A midpoint split can land immediately AFTER a conjunction. MEASURED on real HC3 text:

        "... they had no representation in the British government and. Were being dictated to ..."

    The existing guard only asked what the SECOND half starts with, so this shape — the same broken
    clause, one word to the left — walked straight past it.
    """

    def test_the_conjunction_moves_to_the_second_half(self):
        from untell.rewriter.structural import _split_long_sentences

        long = (
            "They also resented the fact that they had no representation in the British government "
            "and were being dictated to by officials who had no understanding of their needs or "
            "their most basic everyday concerns"
        )
        for _ in range(20):  # the transform is stochastic; the invariant is not
            for out in _split_long_sentences([long], rate=1.0):
                for piece in out.split("."):
                    tail = piece.strip().split()
                    if tail:
                        assert tail[-1].lower() not in {"and", "or", "but", "while", "because"}, out

    def test_mid_phrase_words_are_not_treated_as_split_blockers(self):
        """"that", "which", "who", "if", "for" and "so" open clauses AND sit mid-phrase constantly.

        Including them made things worse: shifting the split point off "that" in "On top of that,
        the clause ..." produced "On top of, that." — a comma inserted where the phrase had none.
        Widened once, measured on 160 rewrites, reverted.
        """
        from untell.rewriter.structural import _SPLIT_CONJUNCTIONS

        assert not _SPLIT_CONJUNCTIONS & {"that", "which", "who", "if", "for", "so"}


class TestRepetitionAwareMerging:
    """Sentences that open identically are merged every time, not at the random rate.

    MEASURED on 12 RAID AI texts through the full loop: repeated_phrasing is the strongest tell
    in the catalogue (AUROC 0.965 RAID / 0.921 HC3) and NO rewriter moved it — 24.83 -> 24.58.
    Repeated sentence openers, by contrast, fell 3.92 -> 0.67 over the same run, because
    structural transforms already vary openings.

    Surgical substitution cannot help: the repeated words are ordinary ("the system is designed
    to"), so they are absent from an AI-vocabulary synonym map. Merging is the transform that
    reaches them, and it is already trusted here for burstiness, so it inherits the existing
    mergeability and meaning checks.

    Effect after the change, same 12 texts: repeated_phrasing 24.83 -> 23.92 and tells/100w
    10.05 -> 8.09 (from 8.70), meaning 0.9941. A real gain, and a small one — recorded honestly
    because the strongest tell remains largely unaddressed by the free rewriters.
    """

    def test_shares_opening_needs_three_words(self):
        """A shared "The" is ordinary English; a shared "The system is" is the pattern."""
        from untell.rewriter.structural import _shares_opening

        assert _shares_opening("The system is fast.", "The system is cheap.")
        assert not _shares_opening("The cat sat.", "The dog ran.")
        assert not _shares_opening("Short one.", "Short two.")  # fewer than 3 words

    def test_shares_opening_is_case_insensitive(self):
        from untell.rewriter.structural import _shares_opening

        assert _shares_opening("The system is fast.", "the system is cheap.")

    def test_identical_openings_merge_even_at_zero_random_rate(self):
        """rate=0 would merge nothing before; a repeated opening must override it."""
        from untell.rewriter.structural import _merge_sentences

        sentences = [
            "The system is designed to improve outcomes. ",
            "The system is designed to reduce cost. ",
        ]
        merged = _merge_sentences(list(sentences), rate=0.0)
        assert len(merged) < len(sentences), "a repeated opening should force the merge"

    def test_distinct_openings_still_respect_the_rate(self):
        """The override must not turn merging on for everything — burstiness depends on it
        staying probabilistic for ordinary pairs."""
        from untell.rewriter.structural import _merge_sentences

        sentences = [
            "The cat sat quietly on the mat. ",
            "A dog barked somewhere down the street. ",
        ]
        assert _merge_sentences(list(sentences), rate=0.0) == sentences


class TestDropRestatements:
    """The only transform found that attacks repeated phrasing at its source.

    MEASURED across 80 RAID pairs, share of sentences whose content words are >=60% covered by an
    earlier sentence: human 0.1%, ai 7.7% (AUROC 0.740). AI also writes 11.8 sentences to the
    human 8.3 for the same source document — that surplus is where the duplicated phrasing lives.

    In ISOLATION on the 21 of 80 texts where it fires:
        repeated_phrasing %  16.01 -> 13.11      tells/100w  18.45 -> 13.77
        words                  320 ->   296      similarity      0.9994
    """

    def test_drops_a_restatement(self):
        from untell.rewriter.structural import _drop_restatements

        sents = [
            "Medical image segmentation is a hard problem in vision. ",
            "We propose a novel approach for medical image segmentation. ",
            "Our approach for medical image segmentation is novel and we propose it. ",
            "Experiments on three datasets show a large gain. ",
            "The method generalises to unseen modalities. ",
        ]
        out = _drop_restatements(list(sents))
        assert len(out) == len(sents) - 1
        assert "Our approach for medical image segmentation is novel" not in "".join(out)

    def test_never_drops_a_sentence_carrying_a_new_numeral(self):
        """A restatement that adds a figure is not a restatement — dropping it loses the fact."""
        from untell.rewriter.structural import _drop_restatements

        sents = [
            "Opening sentence that frames the work. ",
            "The system is fast and cheap to operate. ",
            "The system is fast and cheap across 47 separate trials. ",
            "Unrelated content follows here entirely. ",
            "Final sentence stands alone. ",
        ]
        assert len(_drop_restatements(list(sents))) == len(sents)

    def test_never_drops_a_sentence_holding_a_locked_span(self):
        """A sentinel marks a citation, quote or quantity that exists nowhere else."""
        from untell.rewriter.structural import _drop_restatements

        sents = [
            "Opening sentence that frames the work. ",
            "The system is fast and cheap to operate. ",
            "The system is fast and cheap, per \u27e6HZ0001\u27e7. ",
            "Unrelated content follows here entirely. ",
            "Final sentence stands alone. ",
        ]
        assert len(_drop_restatements(list(sents))) == len(sents)

    def test_never_drops_the_first_or_last_sentence(self):
        """Openers frame and closers conclude; both restate on purpose."""
        from untell.rewriter.structural import _drop_restatements

        sents = [
            "The system is fast and cheap to operate. ",
            "Entirely different content in the middle here. ",
            "More unrelated material to pad the middle out. ",
            "The system is fast and cheap to operate. ",
        ]
        out = _drop_restatements(list(sents))
        assert out[0] == sents[0] and out[-1] == sents[-1]

    def test_removals_are_capped_at_one_per_five_sentences(self):
        """An unlucky pass must not strip a paragraph, but one flat removal left work behind.

        MEASURED over 80 RAID pairs: 40 sentences are droppable in total while a single pass
        reached only 21, because 11 texts carry two to four restatements each. Raising the cap
        took the isolated effect from -18% to -36% on repeated_phrasing with meaning unchanged
        at 0.9994 and still zero human false drops.
        """
        from untell.rewriter.structural import _drop_restatements

        # 7 sentences -> budget 1.
        seven = ["Opening frames the work here. "] + [
            "The system is fast and cheap to operate. " for _ in range(5)
        ] + ["Final sentence stands alone. "]
        assert len(_drop_restatements(list(seven))) == len(seven) - 1

        # 12 sentences -> budget 2, so a text carrying several restatements loses several.
        twelve = ["Opening frames the work here. "] + [
            "The system is fast and cheap to operate. " for _ in range(10)
        ] + ["Final sentence stands alone. "]
        assert len(_drop_restatements(list(twelve))) == len(twelve) - 2

    def test_the_cap_still_bounds_damage(self):
        """However repetitive the input, a single call may never gut it."""
        from untell.rewriter.structural import _drop_restatements

        sents = ["Opening frames the work here. "] + [
            "The system is fast and cheap to operate. " for _ in range(18)
        ] + ["Final sentence stands alone. "]
        out = _drop_restatements(list(sents))
        assert len(out) >= len(sents) - (len(sents) // 5)
        assert len(out) > len(sents) // 2, "a call must never remove most of a paragraph"

    def test_short_input_is_untouched(self):
        from untell.rewriter.structural import _drop_restatements

        sents = ["one here. ", "two here. ", "three here. "]
        assert _drop_restatements(list(sents)) == sents

    def test_does_not_fire_on_varied_human_prose(self):
        """Measured: 0 of 80 human RAID texts had a sentence dropped at the shipped 0.70 bar."""
        from untell.rewriter.structural import _drop_restatements

        sents = [
            "I walked to the shop and it was shut. ",
            "My neighbour said the owner had gone to a funeral in Leeds. ",
            "So I went home and made toast instead. ",
            "Reading the paper took until four in the afternoon. ",
            "The hedge still needed cutting back after that. ",
        ]
        assert _drop_restatements(list(sents)) == sents


class TestClicheFlattening:
    """Clichés were DETECTED and never removed — the audit that found this measured `cliche`
    going 6 -> 6 through the composite loop on 40 AI texts, while formulaic_transition went
    24 -> 4. It is one of only two categories rated STRONG evidence on both corpora (precision
    0.90 HC3, 0.93 RAID), so leaving it untouched was the most valuable gap in the rewriter.

    58 hits across 300 AI texts concentrate in a few forms: "it's important to note" (16),
    "in summary" (14), "in conclusion" (12), "it is important to note" (8), "paves the way" (5).
    After the flattener the same audit gives cliche 6 -> 2.
    """

    @pytest.mark.parametrize(
        ("before", "must_not_contain"),
        [
            ("It is important to note that the results were mixed.", "important to note"),
            ("It's worth noting that costs rose sharply last year.", "worth noting"),
            ("This paves the way for wider adoption.", "paves the way"),
            ("Training plays a crucial role in the outcome.", "crucial role"),
            ("When it comes to safety, the numbers are clear.", "when it comes to"),
            ("The award stands as a testament to careful work.", "testament to"),
        ],
    )
    def test_cliche_is_removed(self, before, must_not_contain):
        from untell.rewriter.structural import _flatten_cliches
        from untell.scripts.tells import score_tells

        after = _flatten_cliches(before)
        assert must_not_contain.lower() not in after.lower()
        assert score_tells(after)["by_category"].get("cliche", 0) == 0

    def test_deletion_restores_the_sentence_capital(self):
        """Removing "It is important to note that " leaves a lower-case word where a sentence now
        starts — a more obvious tell than the cliche was."""
        from untell.rewriter.structural import _flatten_cliches

        out = _flatten_cliches("It is important to note that the results were mixed.")
        assert out[0].isupper(), out

    def test_ordinary_prose_is_untouched(self):
        from untell.rewriter.structural import _flatten_cliches

        text = "The note on the table said the results were mixed, so we ran it again."
        assert _flatten_cliches(text) == text


class TestMergeDoesNotManufactureSemicolons:
    """The rewriter was creating a tell it also counts.

    Sentence merging picked a connector at random from a list that included "; ", and merging runs
    AFTER the semicolon strip, so those survived into the output. semicolon_crutch fires at 2+ per
    passage. MEASURED once repetition-aware merging made merges more frequent: 40 AI texts went
    from 0 semicolons in to 4 out.
    """

    def test_semicolon_is_not_a_connector(self):
        """Asserts the CONSTANT, not its source text.

        This used to `inspect.getsource(_merge_sentences)` and regex out a `connectors = [...]`
        literal, which broke the moment the list moved to module scope to carry frequency weights —
        a refactor that changed nothing about semicolons. Reading the object cannot go stale that
        way, and it also cannot trip on the explanatory comment that quotes "; " while saying why
        it is gone, which is what the source-scraping version was working around.
        """
        from untell.rewriter.structural import _MERGE_CONNECTORS

        offenders = [c for c in _MERGE_CONNECTORS if ";" in c]
        assert not offenders, f"merging can emit a semicolon, a catalogued tell: {offenders}"

    def test_connector_weights_line_up_with_the_connectors(self):
        """The weights are positional, so a connector added without a weight silently shifts every
        later one onto the wrong frequency — and `random.choices` would raise only if the lengths
        differ, not if they are merely misordered."""
        from untell.rewriter.structural import _MERGE_CONNECTORS, _MERGE_WEIGHTS

        assert len(_MERGE_CONNECTORS) == len(_MERGE_WEIGHTS)
        assert abs(sum(_MERGE_WEIGHTS) - 1.0) < 0.01, sum(_MERGE_WEIGHTS)
        # Measured human frequencies: "and" dominates, "though" is nearly absent.
        assert _MERGE_CONNECTORS[0].strip(", ") == "and"
        assert _MERGE_WEIGHTS[0] == max(_MERGE_WEIGHTS)
        assert _MERGE_CONNECTORS[-1].strip(", ") == "though"
        assert _MERGE_WEIGHTS[-1] == min(_MERGE_WEIGHTS)

    def test_emitted_connectors_match_the_human_distribution(self):
        """Uniform choice emitted "though" 29x more often than a human writes it (20% against a
        measured 0.7% over 400 HC3+RAID pairs). An unnatural connective distribution is precisely
        what a perplexity detector reads, so the transform meant to humanise rhythm was leaving its
        own signature."""
        import random
        from collections import Counter

        from untell.rewriter.structural import _MERGE_CONNECTORS, _MERGE_WEIGHTS, _merge_sentences

        sentences = ["The team shipped feature number 1 on time.", "The team shipped it again."]
        seen: Counter = Counter()
        for seed in range(3000):
            random.seed(seed)
            merged = " ".join(_merge_sentences(list(sentences), rate=1.0))
            for c in _MERGE_CONNECTORS:
                if c in merged:
                    seen[c] += 1
                    break
        total = sum(seen.values())
        assert total > 2000, f"merges did not happen often enough to measure: {total}"
        for conn, want in zip(_MERGE_CONNECTORS, _MERGE_WEIGHTS):
            got = seen[conn] / total
            assert abs(got - want) < 0.03, f"{conn!r}: emitted {got:.1%}, want {want:.1%}"

    def test_merging_many_pairs_emits_no_semicolons(self):
        from untell.rewriter.structural import _merge_sentences

        sentences = [f"The team shipped feature number {i} on time. " for i in range(20)]
        merged = "".join(_merge_sentences(sentences, rate=1.0))
        assert ";" not in merged


class TestTheRewriterNeverEmitsACataloguedTell:
    """A replacement whose output is itself in the tell catalogue is a lateral move.

    The rewrite spends its similarity budget, the detector fires on the same span, and the tell
    count does not move — but nothing reports a failure, so it reads as an unexplained residual.
    Three instances were found this way, in three different tables:

        attacks/word_importance._SYN   crucial -> vital, invaluable -> vital,
                                       exceptional -> remarkable, groundbreaking -> pivotal
        _PARTICIPIAL_VERBS             underscoring -> underscores   (ai_vocab)
        _CLICHE_FLATTEN                at the end of the day -> ultimately  (formulaic_transition)

    Two of the three tables run BEFORE _plain_register, so a later pass could sometimes clean up
    after them — but only with probability `intensity * profile["register"]`, and _CLICHE_FLATTEN's
    output lands mid-sentence where _strip_transitions never looks. Emitting a known tell and
    relying on a stochastic later pass is not the same as not emitting it.

    This sweeps every table rather than the ones that happened to be probed, because the failure is
    silent by construction and the next table added will not announce itself.
    """

    @staticmethod
    def _tells_in(fragment: str) -> dict:
        from untell.scripts.tells import score_tells

        # Carried in a two-sentence frame: several catalogue patterns are anchored to a sentence
        # opener or need a preceding sentence, and a bare fragment would miss them.
        probe = f"The team shipped it on time. {fragment[:1].upper()}{fragment[1:]} the plan works."
        return {k: v for k, v in (score_tells(probe, include_matches=True).get("matches") or {}).items()}

    def test_participial_flattening_outputs_are_clean(self):
        from untell.rewriter.structural import _PARTICIPIAL_VERBS

        bad = {k: (v, t) for k, v in _PARTICIPIAL_VERBS.items() if (t := self._tells_in(v))}
        assert not bad, f"flattening a participial trailer into a catalogued tell: {bad}"

    def test_cliche_flattening_outputs_are_clean(self):
        from untell.rewriter.structural import _CLICHE_FLATTEN

        bad = {rep: t for _pat, rep in _CLICHE_FLATTEN if rep.strip() and (t := self._tells_in(rep))}
        assert not bad, f"flattening a cliche into a catalogued tell: {bad}"

    def test_synonym_substitutes_are_clean(self):
        """The same sweep over the vocabulary map, via the rewriter's own view of it.

        test_attacks.py checks this against `ai_vocab` alone; here it is the WHOLE catalogue, so a
        substitute that trips `formulaic_transition` or `hedge_stacking` is caught too.
        """
        from untell.attacks.word_importance import _SYN

        bad = {}
        for key, values in _SYN.items():
            for v in values:
                if t := self._tells_in(v):
                    bad.setdefault(key, []).append((v, t))
        assert not bad, f"substituting one catalogued tell for another: {bad}"


class TestParticipialFlatteningDoesNotRepeatItsOpener:
    """Flattening every trailer to "This <verb>" made one tell into another.

    Five participial trailers in a document became five sentences opening with the same word:

        "This shows ... This reflects ... This confirms ... This indicates ... This suggests ..."

    `score_tells` did NOT flag it — `_duplicate_sentence_starts` needs 40% of sentences and a word
    floor that a short passage misses — which is the point. The catalogue is a proxy for what
    detectors read, not a definition of it, so "our checker is quiet" is not evidence the output is
    good. Repeating one opener five running times is exactly the shape `repeated_sentence_openers`
    exists to name.
    """

    def test_consecutive_trailers_never_share_a_subject(self):
        import random
        import re

        from untell.rewriter.structural import _flatten_participial_trailers

        text = (
            "Sales rose 12 percent, underscoring the strength of demand. "
            "Costs fell sharply, reflecting better logistics. "
            "Margins widened, confirming the turnaround. "
            "Hiring slowed, indicating caution. "
            "Retention improved, suggesting better morale."
        )
        offenders = []
        for seed in range(200):
            random.seed(seed)
            subjects = re.findall(r"\. (This|That|It) ", _flatten_participial_trailers(text))
            assert len(subjects) >= 4, f"seed {seed}: trailers were not flattened: {subjects}"
            if any(a == b for a, b in zip(subjects, subjects[1:])):
                offenders.append((seed, subjects))
        assert not offenders, f"consecutive trailers reused a subject: {offenders[:3]}"

    def test_the_subject_actually_varies(self):
        """The complement: a rotation that always picks the same alternative is still a pattern."""
        import random
        import re

        from untell.rewriter.structural import _flatten_participial_trailers

        text = "Sales rose, underscoring demand. Costs fell, reflecting logistics."
        seen = set()
        for seed in range(60):
            random.seed(seed)
            seen.update(re.findall(r"\. (This|That|It) ", _flatten_participial_trailers(text)))
        assert len(seen) >= 3, f"only {seen} ever appears — the choice is not varying"


class TestOpenerVariationDoesNotRepeatItself:
    """_vary_openers exists to VARY openers, and was the largest source of repeated phrasing.

    MEASURED over 60 RAID+HC3 AI texts, splitting the surviving repeated trigrams by origin:
    93% were inherited from the source (domain terms — "medical image segmentation" — which the
    meaning gates would veto varying anyway), and 7% were CREATED by the rewriter. The single
    largest created repeat was "looking at this" at 7 excess occurrences, ahead of every other.

    Cause: `random.choice` over an 8-item pool, drawn independently per sentence. A long passage
    reuses one. Identical collision to the many-to-one synonym map, and the same fix.
    """

    def test_no_opener_dominates_a_long_passage(self):
        import random
        from collections import Counter

        from untell.rewriter.structural import _vary_openers

        sentences = [
            f"Machine learning models improved metric number {i} substantially this year."
            for i in range(14)
        ]
        worst = 0
        for seed in range(200):
            random.seed(seed)
            out = _vary_openers(list(sentences), rate=1.0)
            counts = Counter(s.split(",")[0] for s in out if "," in s)
            worst = max(worst, max(counts.values()) if counts else 0)
        # 14 sentences over an 8-item pool: 2 is the floor once the pool is exhausted and cycles.
        assert worst <= 2, f"one opener was reused {worst} times in a single passage"

    def test_the_pool_cycles_rather_than_stopping(self):
        """Once every opener is spent the set clears, so a 20-sentence passage keeps varying
        instead of falling back to no variation at all."""
        import random

        from untell.rewriter.structural import _vary_openers

        sentences = [
            f"Machine learning models improved metric number {i} substantially this year."
            for i in range(20)
        ]
        random.seed(0)
        out = _vary_openers(sentences, rate=1.0)
        varied = [s for s in out if "," in s]
        assert len(varied) >= 16, f"variation stopped after the pool emptied: {len(varied)}/20"


class TestTransitionsAreStrippedNotSubstituted:
    """A sentence-initial formulaic transition belongs to _strip_transitions, which DELETES it.

    _plain_register runs first and was substituting them instead, which pre-empts the deletion:
    "Therefore, we adopt it." became "That is why, we adopt it." — a phrase _TRANSITIONS_RE no
    longer matches, so it survived the stripper and then collided with a merge connector to produce

        "results are strong, so that is why, we adopt it."

    A wordier connective is a worse outcome than the word we started with. Mid-sentence occurrences
    are untouched: substitution IS the right move there, and only the sentence-initial position has
    a deletion pass waiting for it.
    """

    @pytest.mark.parametrize(
        "opener", ["Therefore", "Moreover", "Furthermore", "Overall", "Consequently"]
    )
    def test_sentence_initial_transitions_survive_the_register_pass(self, opener):
        import random

        from untell.rewriter.structural import _plain_register

        text = f"{opener}, costs fell sharply."
        for seed in range(20):
            random.seed(seed)
            assert _plain_register(text, 1.0).startswith(opener), (
                f"seed {seed}: the register pass consumed {opener!r}, which _strip_transitions "
                "would have deleted outright"
            )

    def test_mid_sentence_occurrences_are_still_substituted(self):
        """The complement — the guard must be positional, not a blanket exemption."""
        import random

        from untell.rewriter.structural import _plain_register

        text = "The result holds and therefore we adopt it."
        outs = set()
        for seed in range(30):
            random.seed(seed)
            outs.add(_plain_register(text, 1.0))
        assert any("therefore" not in o for o in outs), f"never substituted mid-sentence: {outs}"

    def test_the_whole_pipeline_drops_them_for_a_casual_style(self):
        import random

        from untell.rewriter.structural import structural_rewrite

        text = (
            "Moreover, the model improves accuracy. Furthermore, it reduces cost. "
            "Overall, results are strong. Therefore, we adopt it."
        )
        random.seed(0)
        out = structural_rewrite(text, intensity=1.0, style="casual")
        for marker in ("Moreover", "Furthermore", "Overall", "Therefore"):
            assert marker not in out, f"{marker} survived a casual rewrite: {out}"
        # And the substituted forms must not appear in their place either.
        for wordy in ("What is more", "All told", "that is why", "Plus,"):
            assert wordy not in out, f"transition was substituted rather than stripped: {out}"


class TestAcademicKeepsTheTransitionsHumansUseThere:
    """The same markers point OPPOSITE ways in conversational and academic prose.

    MEASURED per corpus, sentence-opening frequency over 200 pairs each:

                        HC3 (forum Q&A)         RAID (paper abstracts)
                        human      ai           human      ai
        moreover        (<5 occ)                0.888%   0.041%   <- human
        furthermore     (<5 occ)                0.947%   0.332%   <- human
        therefore       (<5 occ)                0.592%   0.000%   <- human
        additionally    0.000%   1.544%         0.178%   0.913%      AI
        overall         0.000%   2.613%         0.000%   2.407%      AI

    Real abstracts use "Moreover"; the generators largely do not. Stripping it from academic prose
    therefore makes the text read LESS human. The exemption is tied to the style profile because
    the fact is corpus-scoped, not universal.
    """

    def test_academic_keeps_the_human_pointing_markers(self):
        import random

        from untell.rewriter.structural import structural_rewrite

        text = (
            "Moreover, the model improves accuracy. Furthermore, it reduces cost. "
            "Therefore, we adopt it."
        )
        kept = 0
        for seed in range(20):
            random.seed(seed)
            out = structural_rewrite(text, intensity=1.0, style="academic")
            kept += sum(m in out for m in ("Moreover", "Furthermore", "Therefore"))
        assert kept > 0, "academic stripped every marker the measurement says humans use there"

    def test_academic_still_strips_the_ai_pointing_markers(self):
        """The exemption is a named set, not a blanket pass — "Overall" points AI in BOTH corpora."""
        import random

        from untell.rewriter.structural import structural_rewrite

        for seed in range(20):
            random.seed(seed)
            out = structural_rewrite(
                "Overall, the programme succeeded. The team was pleased.",
                intensity=1.0,
                style="academic",
            )
            assert "Overall" not in out, f"seed {seed}: kept an AI-pointing marker: {out}"

    def test_no_other_style_carries_the_exemption(self):
        from untell.rewriter.structural import _STYLE_PROFILES, style_profile

        for name in list(_STYLE_PROFILES) + [None, "casual"]:
            keep = style_profile(name)["keep_transitions"]
            if name == "academic":
                assert keep, "academic lost its exemption"
            else:
                assert not keep, f"{name} acquired an unmeasured transition exemption"


class TestOpenersAreOnesHumansActuallyUse:
    """Four of the eight openers appeared 0.000% in BOTH halves of 400 HC3+RAID pairs.

    "Broadly,", "Looking at this,", "As it turns out," and "Realistically," are written by nobody —
    not humans, not the generators. Prepending one is not humanising, it is a fingerprint, and
    _vary_openers fired at ~30% per sentence against a measured 0.2% for the whole set.

    The replacements are chosen on two criteria, not one. Frequency: each is human-leaning by a
    wide margin ("also" 0.568% human / 0.000% AI). Safety: each is content-neutral, because the
    meaning gates check entailment and roles, not discourse relations — so an opener that ASSERTS
    something is a fidelity risk no gate would catch. "so" is the most common human opener in the
    corpus (1.285%) and is declined on exactly that ground: it claims a consequence.
    """

    BANNED = ("Broadly,", "Looking at this,", "As it turns out,", "Realistically,")

    def test_the_unattested_openers_are_gone(self):
        import inspect

        from untell.rewriter.structural import _vary_openers

        src = inspect.getsource(_vary_openers)
        pool = src.split("openers = [", 1)[1].split("]", 1)[0]
        for dead in self.BANNED:
            assert dead not in pool, f"{dead} is written by nobody in either half of the corpus"

    def test_no_opener_asserts_a_relation_the_gates_cannot_check(self):
        """Temporal, causal and deictic markers claim something about the sentence they precede."""
        import inspect

        from untell.rewriter.structural import _vary_openers

        src = inspect.getsource(_vary_openers)
        pool = src.split("openers = [", 1)[1].split("]", 1)[0].lower()
        for unsafe in ("recently,", "meanwhile,", "then,", '"so,"', "here,"):
            assert unsafe not in pool, f"{unsafe} asserts a relation no meaning gate verifies"

    def test_every_opener_is_screened_against_the_catalogue(self):
        """An opener that is itself a tell, or that the later stripper would delete, is wasted."""
        import random

        from untell.rewriter.structural import _TRANSITIONS_RE, _vary_openers
        from untell.scripts.tells import score_tells

        # The fixture has to clear two guards, and the assertion below exists because both are easy
        # to trip silently. "The team shipped ..." fails the first: _vary_openers skips any sentence
        # whose first word is in its `subjects` list (The/This/It/That/There). "Engineering teams
        # ..." fails the second: the opening word must be safe to lowercase, and "Engineering" is
        # neither in _SAFE_TO_LOWERCASE nor attested lowercase elsewhere in the text, so the
        # transform conservatively declines. "Machine" is on the list.
        sentences = [
            f"Machine learning models improved metric number {i} this year." for i in range(40)
        ]
        random.seed(0)
        emitted = {s.split(",")[0] + "," for s in _vary_openers(sentences, rate=1.0) if "," in s}
        assert len(emitted) >= 5, f"pool did not exercise: {emitted}"
        for opener in emitted:
            probe = f"The team shipped it on time. {opener} the plan works."
            tells = score_tells(probe, include_matches=True).get("matches") or {}
            assert not tells, f"{opener!r} is itself a catalogued tell: {tells}"
            assert not _TRANSITIONS_RE.match(f"{opener} x"), (
                f"{opener!r} would be deleted by _strip_transitions — inserting it is wasted work"
            )


class TestContractionInjectionAimsAtTheHumanRateRatherThanMaximising:
    """The function was written on a premise the corpora contradict.

    Its docstring said "AI text contracts far less than human writing". MEASURED per 100 words
    over 200 pairs each:

                     human mean   human median   AI mean   unbounded injection
        HC3            0.666         0.357        0.757          2.263
        RAID           0.045         0.000        0.079          0.215

    AI text contracts at or ABOVE the human rate in both corpora, and unbounded injection took HC3
    text to 3.4x human — its own signature. 46% of human HC3 texts and 94% of human RAID texts
    contain no contraction at all.

    The detectors do not arbitrate this: injection measured +0.0000 (HC3) and -0.0003 (RAID) on the
    full tier over 14 texts each, helping 1 of 14 both times. Recorded because it means this is a
    frequency fix and not a scoring one — and because nothing downstream would have caught it,
    score_tells having no contraction check at all.
    """

    def test_a_long_text_is_not_pushed_far_past_the_human_rate(self):
        from untell.rewriter.structural import _contraction_rate, _inject_contractions

        # 60 contractable clauses: unbounded injection would take this far above any human rate.
        text = " ".join(["The system does not fail and it is ready."] * 60)
        out = _inject_contractions(text)
        rate = _contraction_rate(out)
        assert rate <= 1.5, f"{rate:.2f} per 100 words, against a measured human 0.67"

    def test_text_already_at_the_human_rate_is_left_alone(self):
        from untell.rewriter.structural import _inject_contractions

        # Already contracting well above target — injection must not push it higher.
        text = " ".join(["It's fine and they're ready and we've shipped it."] * 20)
        assert _inject_contractions(text) == text

    def test_a_short_block_still_contracts(self):
        """A rate is a document-level statistic and the pipeline passes one block at a time. On a
        four-word block the budget rounds to 0.027, so a naive cap disables the transform entirely —
        which is how the first version of this cap broke two existing tests."""
        from untell.rewriter.structural import _inject_contractions

        assert _inject_contractions("It is not clear.") == "It isn't clear."
        assert _inject_contractions("Do not stop.") == "Don't stop."

    def test_the_floor_applies_only_to_text_with_no_contraction_at_all(self):
        """The floor exists to mark formal-vs-conversational register, not to top up prose that has
        already made that choice."""
        from untell.rewriter.structural import _CONTRACTED_RE, _inject_contractions

        text = "It's late. The team does not agree."
        before = len(_CONTRACTED_RE.findall(text))
        after = len(_CONTRACTED_RE.findall(_inject_contractions(text)))
        assert after == before, "short text that already contracts was pushed higher"
