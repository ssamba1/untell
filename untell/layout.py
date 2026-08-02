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
_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~)")


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


def _segments(text: str):
    """Partition ``text`` into (kind, prefix, body) triples, in order.

    ``kind`` is "prose" when ``body`` is transformable text, and "layout" when the line must be
    reproduced verbatim (blank lines, fenced code, fence markers). ``prefix`` is a list bullet,
    ordered number, blockquote arrow or ATX heading, re-attached unchanged.

    Both public entry points are built on this so the two can never disagree about where a block
    starts — which they would, being twenty lines apart and easy to edit independently.
    """
    buffer: list[str] = []
    in_fence = False

    def flush():
        if buffer:
            joined = "\n".join(buffer)
            buffer.clear()
            return [("prose", "", joined)]
        return []

    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            yield from flush()
            in_fence = not in_fence
            yield ("layout", "", line)
            continue
        if in_fence or not line.strip():
            yield from flush()
            yield ("layout", "", line)
            continue
        marker = _LINE_MARKER_RE.match(line)
        if marker:
            yield from flush()
            yield ("prose", marker.group(1), marker.group(2))
            continue
        buffer.append(line)
    yield from flush()


def _walk(text: str, transform: Callable[[str], str]) -> str:
    out: list[str] = []
    for kind, prefix, body in _segments(text):
        if kind == "layout":
            out.append(body)
        elif body.strip():
            out.append(prefix + transform(body))
        else:
            out.append(prefix + body)
    return "\n".join(out)
