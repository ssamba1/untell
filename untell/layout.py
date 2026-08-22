"""Apply a text transform without destroying document layout.

Every rewriter that reassembles text ends up doing some form of ``" ".join(sentences)``, which
discards newlines. Run over a paragraph that is invisible; run over a document it returns one wall
of text — paragraph breaks gone, list items merged onto one line, fenced code reflowed into the
surrounding prose, and an ordered-list marker swallowed into the sentence ("1. Install it." became
"1, and in short, and, install it.").

Nothing downstream catches it. The meaning gate compares meaning, the detectors score statistics,
and the tells catalogue matches phrases; none of them looks at layout. So the damage is invisible
to every check in the pipeline and obvious to the first person who reads the output.

Stdlib only — apart from one shared character class imported from ``untell.text_split``, which
is itself stdlib-only and imports nothing from the package — so any rewriter can use it without
a cycle.
"""

from __future__ import annotations

import re
from collections.abc import Callable

# Line-leading markers that carry structure rather than prose: list bullets, ordered-list numbers,
# blockquote arrows and ATX headings. The marker is re-attached verbatim and only the text after it
# is transformed.
_LINE_MARKER_RE = re.compile(r"^([ \t]*(?:[-*+][ \t]+|\d+[.)][ \t]+|>[ \t]?|#{1,6}[ \t]+))(.*)$")
# Capture the whole run, not just the first three characters. A fence closes only on the SAME
# character as its opener and at least as many of them, which is exactly how a document shows
# fenced-code syntax inside a fenced block.
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
# A line ending here finished a sentence, so the newline after it is a boundary the author chose
# rather than a soft wrap to be absorbed. Closers are allowed after the terminator so a line ending
# in a quotation, a parenthesis or a bracket still counts. See the branch in `_segments`.
#
# The terminator class is not ASCII-only: a paragraph-per-line CJK document ends every line in
# 。！？ and an Arabic one in ؟ ۔, and a line ending in one of those is as much a chosen
# boundary as one ending in a full stop. MEASURED before this existed, a two-paragraph CJK
# document came back as ONE block, so the paragraphs were rejoined with spaces when the
# transform ran.
#
# Zero-width carriers may sit between the terminator and the line end (the watermark shape) and
# must not hide the boundary from `\s*$`; the class is the single source in `untell.text_split`
# (docs/free-ceiling-measured.md forbids a second copy).
from untell.text_split import _ZERO_WIDTH_CLASS  # noqa: E402

_SENTENCE_END_RE = re.compile(r"[.!?。！？؟۔][\"')\]”’" + _ZERO_WIDTH_CLASS + r"]*[ \t]*$")
# A THEMATIC BREAK or SETEXT HEADING UNDERLINE is a whole-line construct: `---`, `===`,
# `***`, `___` and the spaced `- - -` / `* * *` forms. It is not prose — a merge
# transform turned "My Heading\\==========" into "My Heading ==========" and welded
# "---" onto the next paragraph ("--- Para two.") — so it is emitted verbatim like a
# table row. The SETEXT underline gets the same treatment as the ATX marker: the heading
# text above it is still prose; the underline itself is layout. Guarded by the fence/
# math/blank branch above, so a `---` inside fenced code stays code.
_HR_RE = re.compile(
    r'^\s*(?:(?:-{3,}|={3,}|\*{3,}|_{3,})|(?:[-*]\s+){2,}[-*])\s*$'
)


def _is_table_row(line: str) -> bool:
    """True when the line is a markdown table row, including inside a blockquote.

    The leading-pipe test is what every markdown table row has and what ordinary prose
    never starts with; a table quoted inside a blockquote starts with the quote arrow
    instead, so peel any number of `>` markers first. Without that, `> | Method |` fell
    through to the marker branch and the CELL CONTENT was handed to the transform — a
    column heading got relabeled (Method -> Technique), which nothing downstream can
    restore. Nested blockquotes (`> > | x |`) peel one arrow at a time.
    """
    s = line.lstrip()
    while s.startswith(">"):
        s = s[1:].lstrip()
    return s.startswith("|")


def apply_per_block(text: str, transform: Callable[[str], str]) -> str:
    """Run ``transform`` over each prose block of ``text``, preserving all layout.

    Consecutive plain lines are gathered into one block, so a soft-wrapped paragraph is transformed
    as a unit — sentence-level work needs more than one sentence in view. Blank lines and fenced
    code pass through untouched. A marked line has only the text after its marker transformed.

    Text containing no newline is handed to ``transform`` directly, so the common single-paragraph
    case is unaffected.
    """
    if "\n" not in text:
        return transform(text)
    # Work in \n and restore the source's own line ending, so a CRLF document does not come back
    # with its line endings silently rewritten.
    crlf = "\r\n" in text
    out = _walk(text.replace("\r\n", "\n"), transform)
    return out.replace("\n", "\r\n") if crlf else out


def blocks(text: str) -> list[str]:
    """The prose units of ``text``, in order, with layout lines and empty units dropped.

    The same partitioning :func:`apply_per_block` uses, exposed for callers that need the UNITS
    rather than a rewritten document. Per-sentence targeting is the case that needs it: it splits on
    sentence terminators, so a bullet list, a transcript or a headings outline — none of which has
    any — collapses to a single unit and the "worst sentences" it reports name the whole document.

    Marked lines keep their marker, because the unit a reader sees includes it.
    """
    out: list[str] = []
    for kind, prefix, body in _segments(text.replace("\r\n", "\n")):
        if kind == "prose" and body.strip():
            out.append(prefix + body)
    return out


def restore_layout_lines(original: str, transformed: str) -> str:
    """Put back every non-prose line of ``original``, by line index.

    For a transform that substitutes words IN PLACE — `surgical` is the one here — this protects
    layout without costing context, which splitting into blocks does. MEASURED over 50 HC3 and RAID
    texts, running `surgical` per block instead of per document left the detector score unchanged
    and made tell removal WORSE: 9.576 -> 10.616 tells/100w on RAID, because a short block scores
    badly and the substitution ranking is only as good as the score it ranks against. Whole-document
    plus this restore keeps the context and still cannot corrupt a code block.

    Line-index alignment is the whole mechanism, so it is checked rather than assumed: over the same
    50 texts and both structured fixtures, `surgical` changed the line count zero times. When the
    counts do differ the transform reflowed, this cannot align, and the transformed text is returned
    untouched — a reflowing transform needs :func:`apply_per_block`, not this.
    """
    src = original.replace("\r\n", "\n").split("\n")
    out = transformed.replace("\r\n", "\n").split("\n")
    if len(src) != len(out):
        return transformed
    mask = _prose_line_mask(original)
    if len(mask) != len(src):  # a classifier/line disagreement is not something to guess through
        return transformed
    merged = [o if keep else s for s, o, keep in zip(src, out, mask)]
    joined = "\n".join(merged)
    return joined.replace("\n", "\r\n") if "\r\n" in original else joined


def _prose_line_mask(text: str) -> list[bool]:
    """One flag per line: True where the line is transformable prose.

    Built on :func:`_segments` rather than beside it, for the reason that function's own docstring
    gives — two partitioners twenty lines apart drift, and this one deciding a line is prose while
    that one decides it is layout is exactly the failure both exist to prevent.
    """
    mask: list[bool] = []
    for kind, _prefix, body in _segments(text.replace("\r\n", "\n")):
        mask.extend([kind == "prose"] * (body.count("\n") + 1))
    return mask


def _segments(text: str):
    """Partition ``text`` into (kind, prefix, body) triples, in order.

    ``kind`` is "prose" when ``body`` is transformable text, and "layout" when the line must be
    reproduced verbatim (blank lines, fenced code, fence markers). ``prefix`` is a list bullet,
    ordered number, blockquote arrow or ATX heading, re-attached unchanged.

    Both public entry points are built on this so the two can never disagree about where a block
    starts — which they would, being twenty lines apart and easy to edit independently.
    """
    buffer: list[str] = []
    # The OPEN fence's marker, or None outside a fence. A bare boolean toggled on any fence marker,
    # so the wrong one closed the block: a ~~~ fence containing a ``` line — the standard way to
    # show fenced-code syntax — ended at the inner backticks, and everything after was handed to
    # the transform as prose. MEASURED: `print("hello")` inside such a block was rewritten.
    fence: str | None = None
    # Display-math state, tracked separately from `fence` for the same reason: `$$` inside a
    # fenced code block is code, not math, and a ```` ``` ```` inside a math block is math, not a
    # fence. A line whose stripped content is exactly `$$` toggles this; anything between the
    # opening and closing `$$` is layout. MEASURED before this existed:
    #
    #     $$
    #     \int_0^1 x dx
    #     $$
    #
    # was one prose block, so the equation — where a rewriter renaming a variable is damage, not
    # improvement — was handed to the transform and rewritten. Inline `$...$` stays prose: it is
    # text with a formula in it, and the inline form is locked by preserve.py's latex_math rule
    # before any rewriter sees it.
    in_math: bool = False
    # True when the PREVIOUS emitted line was a list-item marker and nothing has closed the
    # item since. An indented line is an indented code block only when it BEGINS a block, and
    # the `not buffer` test below was standing in for that -- correctly for a gathered
    # paragraph, and wrongly here, because the marker branch flushes and yields directly
    # without ever appending to `buffer`. So after "- item" the buffer is empty and the
    # item's own continuation line looked exactly like the start of a code block.
    #
    # MEASURED: _segments("- first item\n    continues here\n- second") classified the middle
    # line as layout, so `apply_per_block` returned it verbatim -- the author's own prose was
    # silently excluded from the rewrite with nothing saying so.
    #
    # A blank line closes the item, which is what separates this from a genuine indented code
    # block inside a list ("- item\n\n    code"): that case still reads as layout, correctly.
    after_list_item: bool = False

    def _is_list_marker(prefix: str) -> bool:
        """A bullet or ordered-list marker, NOT a heading or blockquote.

        An indented line after "# Heading" really is a code block, so only list items get the
        continuation treatment.
        """
        return bool(re.match(r"\s*(?:[-*+]|\d+[.)])\s+$", prefix))

    def flush():
        if buffer:
            joined = "\n".join(buffer)
            buffer.clear()
            return [("prose", "", joined)]
        return []

    # YAML front matter: a `---` on the very first line, up to the next `---`. Only at position 0 —
    # a `---` later in a document is a thematic break, and that one is already left alone.
    # MEASURED before this: `title: Moreover the framework` came back as `title: What is more the
    # system`. Document metadata is not prose, and a title is the field most likely to be quoted
    # verbatim somewhere else.
    lines = text.split("\n")
    front_matter_end = -1
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                front_matter_end = i
                break

    for index, line in enumerate(lines):
        if index <= front_matter_end:
            yield from flush()
            yield ("layout", "", line)
            continue
        marker_match = _FENCE_RE.match(line)
        if marker_match:
            run = marker_match.group(1)
            if not in_math:
                if fence is None:
                    yield from flush()
                    fence = run
                elif run[0] == fence[0] and len(run) >= len(fence):
                    fence = None
            # A non-matching marker inside a fence is content; it stays fenced either way, and the
            # line is emitted verbatim in all three cases. Inside a math block a fence marker is
            # MATH too — it must not open or close the fence state, or the block leaks past the
            # closing $$ and locks the prose after it.
            yield ("layout", "", line)
            continue
        # A display-math delimiter. `$$` exactly, not `$$$` (which is a fence-ish artifact) and
        # not `$...$` inline math (which stays prose). Emitted verbatim as layout on both sides,
        # so the content between the delimiters is protected by the `in_math` branch below.
        # Guarded by `fence is None`: a `$$` inside a fenced code block is CODE, not math, and
        # toggling here would leave the math state stuck open (or closed) past the fence's end,
        # swallowing the prose after it.
        if fence is None and line.strip() == "$$":
            yield from flush()
            in_math = not in_math
            yield ("layout", "", line)
            continue
        if fence is not None or in_math or not line.strip():
            # A blank line closes the list item, so what follows may be a code block again.
            after_list_item = False
            yield from flush()
            yield ("layout", "", line)
            continue
        # A TABLE ROW is structure and data, not prose. It has no line marker, so it was gathered
        # into the surrounding block and rewritten as a paragraph. MEASURED on a document ending in
        # a results table, at every seed tried:
        #
        #     | Method | Score |   ->   | Way | Score |   /   | Approach | Score |   /   | Technique |
        #
        # A column heading is a label the surrounding text refers to and often a term of art, and
        # nothing downstream can restore it. The cells are worse in principle than the heading: a
        # sentence-level transform gathering several rows into one block is free to merge or split
        # across the pipes, which would destroy the table rather than relabel it.
        #
        # The test is the leading pipe, which is what every markdown table row and delimiter row
        # has and what ordinary prose never starts with.
        if _is_table_row(line):
            yield from flush()
            yield ("layout", "", line)
            continue
        # A thematic-break or setext-underline line is layout too (see _HR_RE). Must come
        # before the marker branch: the spaced form "- - -" otherwise matches the bullet
        # marker and is treated as a list item.
        if _HR_RE.match(line):
            yield from flush()
            yield ("layout", "", line)
            continue
        # An INDENTED CODE BLOCK — four spaces or a tab, starting a block. MEASURED before this,
        # at every seed:
        #
        #         def f():
        #             return utilize(x)
        #       ->
        #     def f():
        #             return use(x)
        #
        # Both halves of that are damage. The identifier was renamed, and the first line lost its
        # indent, so what is left is not a code block at all — it renders as prose. The fenced form
        # has been protected since this module was written; the indented form is the same construct
        # and had nothing.
        #
        # `not buffer` is what keeps this off a soft-wrapped paragraph's continuation lines: an
        # indented line only starts code when it BEGINS a block, which after a blank line it does.
        # A line indented in the middle of a gathered paragraph stays prose, which is what a wrapped
        # paragraph in a list item looks like.
        # A list item's own CONTINUATION line, indented under its marker with no blank line
        # between. That is prose the author wrapped, not code. The indent is carried as a
        # prefix and re-attached, exactly as a list marker is, so the transform sees only the
        # words.
        if after_list_item and not buffer and (
            line.startswith("    ") or line.startswith("\t")
        ):
            stripped = line.lstrip(" \t")
            yield ("prose", line[: len(line) - len(stripped)], stripped)
            continue
        if not buffer and (line.startswith("    ") or line.startswith("\t")):
            after_list_item = False
            yield ("layout", "", line)
            continue
        # A list-item marker must be extracted BEFORE the hard-break check fires. A list item
        # whose body ends in two trailing spaces — "- item  " — is a hard break, but the marker
        # "- " still needs to be separated from the body "item  " so the transform receives only
        # the body. Without this ordering, the hard-break branch catches "- item  " first, yields
        # ("prose", "", "- item  "), and `_walk` passes "- item" to the transform — the bullet is
        # inside the transform's input, inconsistent with how every other list item is handled.
        # MEASURED before the fix: apply_per_block("- item  \n- normal", upper) produced
        # "[- ITEM]  \n- [NORMAL]" — the bullet was capitalised for the hard-break item.
        marker = _LINE_MARKER_RE.match(line)
        if marker:
            yield from flush()
            after_list_item = _is_list_marker(marker.group(1))
            yield ("prose", marker.group(1), marker.group(2))
            continue
        # A markdown HARD BREAK — two or more trailing spaces — is not a soft wrap. It is the
        # author saying "render a line break here", and gathering it into the surrounding block
        # lets a sentence-level transform merge straight across it. MEASURED: two lines joined by a
        # hard break came back as one sentence, "The system taps into a strong method here, but it
        # delivers outcomes at scale today." The break survives when nothing else changes, which is
        # what made it easy to miss — it only disappears once the merge transform fires.
        #
        # Ending the block here costs the transform some context (the next line is rewritten on its
        # own), and that is the right trade: the author asked for a boundary, so this module's job
        # is to honour it rather than to optimise across it.
        if line.endswith("  "):
            buffer.append(line)
            yield from flush()
            continue
        # A line that ENDS A SENTENCE is a boundary too. Gathering consecutive plain lines assumes
        # they are a soft-wrapped paragraph, and for text that puts one paragraph per line — which
        # is how chat models and forum answers are usually pasted — that assumption deletes the
        # paragraph breaks: the block is rejoined with " " and the separators never come back.
        #
        # MEASURED end to end on HC3 answers, before this branch existed: 3 of 4 documents came
        # back as a single paragraph (3 -> 1, 3 -> 1, 4 -> 1). The module's docstring promises
        # "preserving all layout" and "the original separators are restored verbatim", and nothing
        # downstream objects — the meaning gate compares meaning, the detectors score statistics,
        # and neither looks at layout.
        #
        # The two cases separate cleanly on the last character. Over 12 HC3 documents, 34 of 34
        # non-final lines end in sentence-terminating punctuation; in genuinely soft-wrapped prose
        # 0 of 2 do, because a soft wrap breaks mid-clause. So this keeps hard-wrapped paragraphs
        # gathered while leaving paragraph-per-line documents intact.
        #
        # Same trade as the hard-break branch above, for the same reason: the block ends, so the
        # transform sees less context, and honouring a boundary the author put there beats
        # optimising across it.
        # AFTER the marker branch, deliberately. A list item ends in a full stop as often as a
        # paragraph does, so testing this first swallowed "- Furthermore, it is robust." into the
        # prose buffer with its bullet attached — `blocks()` strips the marker and `apply_per_block`
        # did not, and the two partitions disagreed. Their agreement test caught it.
        if _SENTENCE_END_RE.search(line):
            buffer.append(line)
            yield from flush()
            continue
        buffer.append(line)
    yield from flush()


def _walk(text: str, transform: Callable[[str], str]) -> str:
    out: list[str] = []
    for kind, prefix, body in _segments(text):
        if kind == "layout":
            out.append(body)
        elif body.strip():
            # A hard break lives in trailing whitespace, and every transform strips it — so the
            # block came back one line but rendering as a soft wrap, which is the same loss by a
            # different route. Hold the marker aside and re-attach it.
            hard_break = "  " if body.endswith("  ") else ""
            out.append(prefix + transform(body.rstrip() if hard_break else body) + hard_break)
        else:
            out.append(prefix + body)
    return "\n".join(out)
