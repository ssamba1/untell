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


def _read_text(path: str) -> str:
    for encoding in _TEXT_ENCODINGS:
        try:
            with open(path, encoding=encoding) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
    # Nothing decoded cleanly. Only now accept lossy replacement, and say so — the previous
    # behaviour applied errors="replace" immediately, so a cp1252 file (Word's default on Windows)
    # silently became mojibake: every smart quote and em-dash turned into U+FFFD before scoring.
    logger.warning("%s: could not decode with %s; falling back to lossy replacement.",
                   path, ", ".join(_TEXT_ENCODINGS))
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


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
