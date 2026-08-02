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


def _walk(text: str, transform: Callable[[str], str]) -> str:
    out: list[str] = []
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        if buffer:
            out.append(transform("\n".join(buffer)))
            buffer.clear()

    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            flush()
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or not line.strip():
            flush()
            out.append(line)
            continue
        marker = _LINE_MARKER_RE.match(line)
        if marker:
            flush()
            prefix, body = marker.group(1), marker.group(2)
            out.append(prefix + (transform(body) if body.strip() else body))
            continue
        buffer.append(line)
    flush()
    return "\n".join(out)
