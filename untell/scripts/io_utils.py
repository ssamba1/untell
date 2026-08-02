"""Input readers — plain text, plus .docx and .pdf when the optional ``[docs]`` extra is installed."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Encodings tried in order before falling back to lossy replacement. cp1252 covers the smart quotes,
# em-dashes and ellipses that Word and most Windows editors emit — precisely the characters an
# AI-tells scorer cares about, and precisely what errors="replace" would destroy.
# utf-8-sig FIRST: it decodes plain UTF-8 identically but also strips a leading BOM. With plain
# utf-8 first, a BOM-prefixed file decodes "successfully" and leaves U+FEFF as the first
# character of the text — an invisible char the scorer then sees as content.
_TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

# Byte-order marks, longest first — the UTF-32-LE mark (FF FE 00 00) starts with the UTF-16-LE mark
# (FF FE), so checking UTF-16 first would truncate every UTF-32 file to garbage.
#
# Sniffing these is not a nicety. `latin-1` is last in the list above and it maps every one of the
# 256 byte values, so it CANNOT raise UnicodeDecodeError — the loop always "succeeds" there. That
# made the lossy-replacement branch below unreachable dead code, and, far worse, meant a UTF-16
# file (what Windows "Save as -> Unicode" writes) decoded silently into mojibake:
#     'The "smart quotes"'  ->  'ÿþT\x00h\x00e\x00 \x00"\x00s\x00m\x00a\x00r\x00t\x00...'
# and was then scored and rewritten as if that were the user's prose.
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)

# Real text files contain no NUL at all, so a single one means the content is binary or was decoded
# with the wrong codec. Rejecting on any NUL is deliberately strict: the alternative is scoring and
# rewriting mojibake, and this module already prefers a clear error over plausible garbage (see the
# scanned-PDF branch).


def _read_docx(path: str) -> str:
    from docx import Document  # python-docx

    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    # Document.paragraphs does NOT descend into tables, so a document whose content lives in a table
    # (very common for reports, forms and CVs) previously read as empty or near-empty and was then
    # scored/humanized as if that text did not exist.
    for table in getattr(doc, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if para.text.strip():
                        parts.append(para.text)
    return "\n".join(parts)


def _read_pdf(path: str) -> str:
    from pypdf import PdfReader

    pages = PdfReader(path).pages
    texts = [(page.extract_text() or "") for page in pages]
    empty = sum(1 for t in texts if not t.strip())
    if pages and empty == len(pages):
        # Every page yielded nothing: this is a scanned/image PDF and pypdf cannot read it. Returning
        # "" would hand an empty string to the scorer, which would happily report it as clean text.
        raise ValueError(
            f"{path}: no extractable text — this looks like a scanned/image PDF. "
            "Run OCR first (e.g. ocrmypdf) and retry."
        )
    if empty:
        logger.warning(
            "%s: %d of %d pages yielded no text (likely scanned images); the extracted text is "
            "PARTIAL.", path, empty, len(pages),
        )
    return "\n".join(texts)


def _reject_if_binary(path: str, text: str) -> str:
    """Refuse content that decoded "successfully" but is plainly not prose.

    Because latin-1 accepts any byte, a binary file reads back as a string and would be scored as
    text — the detector would report a number for it. Returning garbage is worse than failing.
    """
    if "\x00" in text:
        raise ValueError(
            f"{path}: decoded text contains NUL bytes — this is a binary file, or text in an "
            "encoding this reader could not identify. Convert it to UTF-8 and retry."
        )
    return text


def _read_text(path: str) -> str:
    with open(path, "rb") as fh:
        head = fh.read(4)
    # A byte-order mark is unambiguous: use it rather than guessing. Without this, UTF-16/UTF-32
    # files fell through to latin-1 (which cannot fail) and became mojibake, silently.
    for bom, encoding in _BOMS:
        if head.startswith(bom):
            try:
                with open(path, encoding=encoding) as fh:
                    return _reject_if_binary(path, fh.read())
            except UnicodeDecodeError:
                break  # BOM present but the body does not decode — fall through to the guesses

    for encoding in _TEXT_ENCODINGS:
        try:
            with open(path, encoding=encoding) as fh:
                text = fh.read()
        except UnicodeDecodeError:
            continue
        if encoding == "latin-1":
            # Reached only because every stricter codec failed. latin-1 cannot fail, so arriving
            # here is not evidence the result is right — say so instead of returning it silently.
            logger.warning(
                "%s: decoded as latin-1 only because it maps every byte; %s all failed. If this "
                "file is not Latin-1 the text is mojibake. Convert it to UTF-8 to be sure.",
                path, ", ".join(_TEXT_ENCODINGS[:-1]),
            )
        return _reject_if_binary(path, text)

    # Unreachable while latin-1 is in the list, but kept so removing it degrades safely.
    logger.warning("%s: could not decode with %s; falling back to lossy replacement.",
                   path, ", ".join(_TEXT_ENCODINGS))
    with open(path, encoding="utf-8", errors="replace") as fh:
        return _reject_if_binary(path, fh.read())


def read_file(path: str) -> str:
    """Read text from a file. Handles .docx (python-docx) and .pdf (pypdf) if installed, else text."""
    low = path.lower()
    if low.endswith(".docx"):
        return _read_docx(path)
    if low.endswith(".pdf"):
        return _read_pdf(path)
    return _read_text(path)


def configure_utf8_io() -> None:
    """Force UTF-8 on stdin/stdout/stderr so non-ASCII text never crashes a Windows console.

    Windows defaults the standard streams to the locale code page (commonly cp1252); piping or
    printing emoji / accented / RTL text then raises ``UnicodeDecodeError``/``UnicodeEncodeError``.
    Each stream is reconfigured independently and best-effort (a replaced stream in tests may lack
    ``reconfigure`` — that is fine, it is skipped).
    """
    import sys

    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
