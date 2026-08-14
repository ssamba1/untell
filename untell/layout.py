"""Apply a text transform without destroying document layout.

Every rewriter that reassembles text ends up doing some form of ``" ".join(sentences)``, which
discards newlines. Run over a paragraph that is invisible; run over a document it returns one wall
of text — paragraph breaks gone, list items merged onto one line, fenced code reflowed into the
surrounding prose, and an ordered-list marker swallowed into the sentence ("1. Install it." became
"1, and in short, and, install it.").

Nothing downstream catches it. The meaning gate compares meaning, the detectors score statistics,
and the tells catalogue matches phrases; none of them looks at layout. So the damage is invisible
to every check in the pipeline and obvious to the first person who reads the output.

Stdlib only, and it imports nothing from the package, so any rewriter can use it without a cycle.
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
_SENTENCE_END_RE = re.compile(r"[.!?][\"')\]”’]*[ \t]*$")


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
    if len(mask) == len(src):  # a classifier/line disagreement is not something to guess through
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
            if fence is None:
                yield from flush()
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
            # A non-matching marker inside a fence is content; it stays fenced either way, and the
            # line is emitted verbatim in all three cases.
            yield ("layout", "", line)
            continue
        # A display-math delimiter. `$$` exactly, not `$$$` (which is a fence-ish artifact) and
        # not `$...$` inline math (which stays prose). Emitted verbatim as layout on both sides,
        # so the content between the delimiters is protected by the `in_math` branch below.
        if line.strip() == "$$":
            yield from flush()
            in_math = not in_math
            yield ("layout", "", line)
            continue
        if fence is not None or in_math or not line.strip():
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
        if line.lstrip().startswith("|"):
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
        if not buffer and (line.startswith("    ") or line.startswith("\t")):
            yield ("layout", "", line)
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
        marker = _LINE_MARKER_RE.match(line)
        if marker:
            yield from flush()
            yield ("prose", marker.group(1), marker.group(2))
            continue
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
