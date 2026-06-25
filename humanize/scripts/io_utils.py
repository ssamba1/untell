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
    with open(path, encoding="utf-8") as fh:
        return fh.read()
