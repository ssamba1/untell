"""A doc whose first line is not --- must not be scanned as front matter.

layout.py:156: `if lines and lines[0].strip() == "---"` — front-matter scanning
requires the FIRST line to be exactly "---". The mutation and -> or scans any
non-empty doc for a "---"/"..." terminator, so a normal doc containing "..." on
line 2 ("Hello\n...\nWorld") treats it as front matter and the lines before the
terminator are consumed as layout — the prose vanishes from blocks().
"""
from untell.layout import blocks


def test_non_front_matter_doc_is_not_consumed():
    assert blocks("Hello\n...\nWorld") == ["Hello\n...", "World"]


def test_real_front_matter_is_excluded_from_prose():
    result = blocks("---\ntitle: X\n---\nBody text")
    assert result == ["Body text"], result
