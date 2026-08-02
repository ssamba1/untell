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


class TestBlocksExposesTheUnits:
    """`blocks()` is the same partitioning as apply_per_block, for callers that need the units.

    Per-sentence targeting is the case that needs it: it splits on sentence terminators, and a
    bullet list, transcript or headings outline has none, so the whole document came back as one
    "sentence" and the worst-sentence list named all of it. Measured at 40 lines each, units before
    the fix: bullets 1, headings 1, transcript 1, semicolon run-on 1 — against 40 for prose.
    """

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
        from untell.layout import apply_per_block, blocks

        from untell.layout import _LINE_MARKER_RE

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
