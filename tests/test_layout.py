"""Document layout must survive every rewriter.

Each rewriter that reassembles text ends up doing some form of ``" ".join(sentences)``, which
discards newlines. Over a paragraph that is invisible; over a document it returns one wall of text.
Six of the nine rewriters did it, and nothing downstream noticed — the meaning gate compares
meaning, the detectors score statistics, the tells catalogue matches phrases, and none of them
looks at layout.

Parametrized over the registry rather than written per rewriter, so one added later is covered
without being remembered.
"""

from __future__ import annotations

import random

import pytest

from untell.layout import apply_per_block

FENCE = "```"
CODE = "x = compute(1, 2)"
DOC = (
    "# Overview\n"
    "\n"
    "Furthermore, the system leverages robust methodologies to optimize outcomes.\n"
    "\n"
    "- Furthermore, it is robust.\n"
    "- Moreover, it is seamless.\n"
    "\n"
    f"{FENCE}python\n{CODE}\n{FENCE}\n"
    "\n"
    "> Moreover, the analysis holds.\n"
    "\n"
    "1. Furthermore, install it.\n"
    "2. Moreover, configure it.\n"
)

REWRITERS = ["structural", "surgical", "composite", "targeted", "ensemble", "neural", "max",
             "t5_paraphrase", "mt_pivot"]


def _shape(t: str) -> dict:
    lines = t.split("\n")
    return {
        "blank": sum(1 for x in lines if not x.strip()),
        "bullets": sum(1 for x in lines if x.startswith("- ")),
        "numbered": sum(1 for x in lines if x[:2] in ("1.", "2.")),
        "headings": sum(1 for x in lines if x.startswith("#")),
        "quotes": sum(1 for x in lines if x.startswith("> ")),
        "fences": t.count(FENCE),
    }


@pytest.mark.parametrize("name", REWRITERS)
def test_rewriter_preserves_document_layout(name):
    from untell.rewriter import get_rewriter

    rw = get_rewriter(prefer=name)
    if rw is None:
        pytest.skip(f"{name} unavailable (optional dependency)")

    random.seed(0)
    out = rw.rewrite(DOC, {"max": 0.9, "tier": "lite"}, 0.30)
    assert isinstance(out, str)
    assert _shape(out) == _shape(DOC), f"{name} changed the layout:\n{out}"
    assert CODE in out, f"{name} rewrote fenced code:\n{out}"


# ---------------------------------------------------------------------------
# The shared helper
# ---------------------------------------------------------------------------


def test_single_paragraph_bypasses_the_walker_entirely():
    """The common case must be unchanged: no newline means the transform sees the whole string."""
    seen = []
    out = apply_per_block("one paragraph, no newlines", lambda b: seen.append(b) or b.upper())
    assert seen == ["one paragraph, no newlines"]
    assert out == "ONE PARAGRAPH, NO NEWLINES"


def test_soft_wrapped_lines_are_one_block():
    """Sentence-level work needs more than one sentence in view, so consecutive plain lines are
    transformed together rather than line by line."""
    seen = []
    apply_per_block("first line\nsecond line\n\nnext para", lambda b: seen.append(b) or b)
    assert seen == ["first line\nsecond line", "next para"]


def test_markers_are_reattached_verbatim():
    """"1. Install it." became "1, and in short, and, install it." — the marker was swallowed into
    the sentence as if it were a numeral in the prose."""
    seen = []
    out = apply_per_block(
        "- bullet body\n1. numbered body\n> quoted body\n## heading body",
        lambda b: seen.append(b) or "REWRITTEN",
    )
    assert seen == ["bullet body", "numbered body", "quoted body", "heading body"]
    assert out == "- REWRITTEN\n1. REWRITTEN\n> REWRITTEN\n## REWRITTEN"


def test_fenced_code_is_never_passed_to_the_transform():
    seen = []
    src = f"prose here\n\n{FENCE}python\nx = 1\ny = 2\n{FENCE}\n\nmore prose"
    out = apply_per_block(src, lambda b: seen.append(b) or "REWRITTEN")
    assert seen == ["prose here", "more prose"]
    assert "x = 1\ny = 2" in out


def test_blank_lines_and_trailing_newline_survive():
    src = "a\n\n\nb\n"
    assert apply_per_block(src, lambda b: b) == src


def test_crlf_is_restored():
    src = "first line.\r\n\r\nsecond line.\r\n"
    out = apply_per_block(src, lambda b: b)
    assert out == src
    assert "\n" not in out.replace("\r\n", "")


def test_unterminated_fence_does_not_swallow_the_rest_silently():
    """An opening fence with no close means everything after it is code, which is what a markdown
    renderer does too — the point is that it must not crash or lose text."""
    src = f"prose\n\n{FENCE}\nx = 1\ny = 2"
    out = apply_per_block(src, lambda b: "REWRITTEN")
    assert "x = 1" in out and "y = 2" in out


class TestAFenceClosesOnlyOnItsOwnMarker:
    """The walker toggled a boolean on ANY fence marker, so the wrong one closed the block.

    Markdown closes a fence only with the SAME character as its opener, and at least as many of
    them. A ~~~ block containing a ``` line — the standard way to show fenced-code syntax inside a
    document — therefore ended at the inner backticks, and everything after it went to the
    transform as prose. MEASURED: `print("hello")` inside such a block was rewritten.
    """

    def test_a_backtick_fence_does_not_close_a_tilde_fence(self):
        seen = []
        src = 'prose\n\n~~~\nwrite:\n```\nprint("hello")\n```\ndone.\n~~~\n\nmore prose'
        out = apply_per_block(src, lambda b: seen.append(b) or "REWRITTEN")
        assert seen == ["prose", "more prose"]
        assert 'print("hello")' in out
        assert "write:" in out and "done." in out

    def test_a_tilde_fence_does_not_close_a_backtick_fence(self):
        seen = []
        src = "prose\n\n```\n~~~\nx = 1\n~~~\n```\n\nmore prose"
        out = apply_per_block(src, lambda b: seen.append(b) or "REWRITTEN")
        assert seen == ["prose", "more prose"]
        assert "x = 1" in out

    def test_a_shorter_run_does_not_close_a_longer_one(self):
        """```` opens; the ``` inside it is content, exactly as a renderer treats it."""
        seen = []
        src = 'prose\n\n````\n```\nprint("inner")\n```\n````\n\nmore prose'
        out = apply_per_block(src, lambda b: seen.append(b) or "REWRITTEN")
        assert seen == ["prose", "more prose"]
        assert 'print("inner")' in out

    def test_a_longer_run_still_closes_a_shorter_one(self):
        seen = []
        src = "prose\n\n```\nx = 1\n`````\n\nmore prose"
        out = apply_per_block(src, lambda b: seen.append(b) or "REWRITTEN")
        assert seen == ["prose", "more prose"]
        assert "x = 1" in out

    def test_every_line_survives_verbatim(self):
        src = 'a\n\n~~~\n```\ncode\n```\n~~~\n\nb\n'
        assert apply_per_block(src, lambda b: b) == src

    def test_blocks_agrees_with_apply_per_block(self):
        """Both entry points are built on one partitioner; pin that they see the same fence."""
        from untell.layout import blocks

        src = 'prose one\n\n~~~\n```\ncode\n```\n~~~\n\nprose two'
        assert blocks(src) == ["prose one", "prose two"]


class TestBlocksExposesTheUnits:
    """`blocks()` is the same partitioning as apply_per_block, for callers that need the units.

    Per-sentence targeting is the case that needs it: it splits on sentence terminators, and a
    bullet list, transcript or headings outline has none, so the whole document came back as one
    "sentence" and the worst-sentence list named all of it. Measured at 40 lines each, units before
    the fix: bullets 1, headings 1, transcript 1, semicolon run-on 1 — against 40 for prose.

    Only the MARKER cases are fixed by this, and deliberately so. Re-measured through
    score_sentences: bullets 4/4, headings 5/5, numbered 4/4 — but a transcript still comes back as
    one unit and so does a semicolon run-on, because both are genuinely one contiguous prose region:
    `blocks()` gathers consecutive unmarked lines on purpose, so a soft-wrapped paragraph is not
    shredded into lines. "This whole run-on sentence reads as AI" is useful advice; "this whole
    document reads as AI" was not, and that is the difference the fix targets.
    """

    @pytest.mark.parametrize(
        ("label", "doc", "expected_units"),
        [
            ("bullets", "- leverage robust methods\n- utilize frameworks\n- foster collaboration", 3),
            ("headings", "# Summary\n## Findings\n## Method\n## Conclusion", 4),
            ("numbered", "1. delve into the data\n2. navigate the landscape\n3. showcase results", 3),
            # NOT split, on purpose — one contiguous prose region either way.
            ("transcript", "ALICE: ship it\nBOB: not yet\nALICE: tests passed\nBOB: fine", 1),
            ("semicolon run-on", "It is robust; it scales; it delivers; it fosters innovation", 1),
        ],
    )
    def test_score_sentences_sees_the_units_a_reader_would(self, label, doc, expected_units):
        """The end-to-end consequence: the worst-sentence list must name a PART of the document.

        Asserted through score_sentences rather than blocks(), because the docstring's claim is
        about what per-sentence targeting reports, and a partitioner that is right in isolation is
        worth nothing if its consumer does not use it.
        """
        from untell.scripts.sentences import score_sentences

        result = score_sentences(doc, tier="lite", threshold=0.30)
        assert len(result["sentences"]) == expected_units, result["sentences"]

    def test_markers_become_separate_units_with_their_marker_kept(self):
        from untell.layout import blocks

        src = "- first item\n- second item\n- third item"
        assert blocks(src) == ["- first item", "- second item", "- third item"]

    def test_headings_become_separate_units(self):
        from untell.layout import blocks

        src = "## Section one\n## Section two"
        assert blocks(src) == ["## Section one", "## Section two"]

    def test_soft_wrapped_lines_stay_one_unit(self):
        """The reason blocks() cannot simply split on newlines: a wrapped paragraph is one unit,
        and splitting it would hand the caller half-sentences."""
        from untell.layout import blocks

        src = "This sentence is wrapped\nacross two lines but is one\nsentence all the same."
        assert blocks(src) == ["This sentence is wrapped\nacross two lines but is one\nsentence all the same."]

    def test_blank_lines_separate_units(self):
        from untell.layout import blocks

        assert blocks("first para\n\nsecond para") == ["first para", "second para"]

    def test_fenced_code_is_not_a_unit(self):
        from untell.layout import blocks

        src = f"prose here\n\n{FENCE}\nx = 1\n{FENCE}\n\nmore prose"
        assert blocks(src) == ["prose here", "more prose"]

    def test_empty_and_whitespace_yield_nothing(self):
        from untell.layout import blocks

        assert blocks("") == []
        assert blocks("   \n\n  ") == []

    def test_single_paragraph_is_one_unit(self):
        from untell.layout import blocks

        assert blocks("Just one line here.") == ["Just one line here."]

    def test_blocks_and_apply_per_block_agree_on_where_units_start(self):
        """Both are built on one partitioner, so they cannot drift apart."""
        from untell.layout import _LINE_MARKER_RE, apply_per_block, blocks

        src = DOC
        seen: list[str] = []
        apply_per_block(src, lambda b: seen.append(b) or b)
        # apply_per_block sees marker BODIES; blocks() re-attaches the marker. Strip with the
        # module's own pattern rather than a hand-rolled one, which is how this test first got the
        # "# " heading prefix wrong.
        stripped = []
        for b in blocks(src):
            m = _LINE_MARKER_RE.match(b)
            stripped.append(m.group(2) if m else b)
        assert stripped == seen


class TestSetextHeadingsAndThematicBreaks:
    """ATX headings are marked lines, but the SETEXT underline ("Heading\\n======") and the
    thematic break ("---" between paragraphs) had no branch of their own: both were
    gathered into the surrounding prose block, so a merge transform turned
    "My Heading\\n==========" into "My Heading ==========" and welded the break onto the
    next paragraph ("--- Para two."). MEASURED before the fix (probe slice-4). Both are
    whole-line layout constructs now, emitted verbatim.
    """

    @pytest.mark.parametrize("underline", ["==========", "----------", "**********", "__________"])
    def test_a_setext_underline_is_never_passed_to_the_transform(self, underline):
        src = f"My Heading\n{underline}\nSome prose here. More prose."
        seen: list[str] = []
        apply_per_block(src, lambda b: seen.append(b) or b)
        assert seen == ["My Heading", "Some prose here. More prose."]
        out = apply_per_block(src, lambda b: "REWRITTEN")
        assert underline in out

    @pytest.mark.parametrize("hr", ["---", "***", "___", "- - -", "* * *"])
    def test_a_thematic_break_between_paragraphs_is_layout(self, hr):
        from untell.layout import blocks

        src = f"Para one.\n{hr}\nPara two."
        assert blocks(src) == ["Para one.", "Para two."]
        out = apply_per_block(src, lambda b: " ".join(b.split()))
        assert hr in out
        assert f"Para one.{hr}" not in out.replace("\n", " ")

    def test_a_setext_heading_survives_a_merge_transform(self):
        src = "My Heading\n==========\nSome prose here. More prose."
        out = apply_per_block(src, lambda b: " ".join(x.strip() for x in b.split("\n")))
        assert "==========" in out
        assert "My Heading ==========" not in out

    def test_the_heading_text_above_a_setext_underline_is_still_prose(self):
        seen: list[str] = []
        apply_per_block("My Heading\n==========", lambda b: seen.append(b) or b)
        assert seen == ["My Heading"]


class TestBlockquotedTablesAreLayout:
    """The pipe-row branch tested the leading pipe, so a table inside a blockquote
    (`> | Method | Score |`) fell through to the marker branch and the CELL CONTENT was
    handed to the transform — a column heading got relabeled (Method -> Technique),
    which nothing downstream can restore. MEASURED before the fix (probe slice-4).
    """

    def test_a_blockquoted_table_row_is_never_passed_to_the_transform(self):
        src = "> | Method | Score |\n> |--------|-------|\n> | A | 0.9 |"
        seen: list[str] = []
        out = apply_per_block(src, lambda b: seen.append(b) or b.replace("Method", "Technique"))
        assert seen == []
        assert out == src

    def test_a_nested_blockquoted_table_row_too(self):
        src = "> > | Method | Score |\n> > | A | 0.9 |"
        assert apply_per_block(src, lambda b: "REWRITTEN") == src

    def test_blockquote_prose_is_still_prose(self):
        seen: list[str] = []
        apply_per_block("> Some prose here. More prose.\n> And another line.", lambda b: seen.append(b) or b)
        assert seen == ["Some prose here. More prose.", "And another line."]
