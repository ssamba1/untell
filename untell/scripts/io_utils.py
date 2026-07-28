"""Input readers — plain text, plus .docx and .pdf when the optional ``[docs]`` extra is installed."""

from __future__ import annotations


def read_file(path: str) -> str:
    """Read text from a file. Handles .docx (python-docx) and .pdf (pypdf) if installed, else UTF-8."""
    low = path.lower()
    if low.endswith(".docx"):
        from docx import Document  # python-docx

        return "\n".join(p.text for p in Document(path).paragraphs)
    if low.endswith(".pdf"):
        from pypdf import PdfReader

        return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


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
