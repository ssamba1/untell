"""Tests for io_utils — UTF-8 configuration and stdin helpers."""
from __future__ import annotations

import io
import sys

from untell.scripts.io_utils import configure_utf8_io


class TestConfigureUtf8Io:
    """Must not crash on any platform, and must configure stdout/stderr for UTF-8."""

    def test_returns_none(self):
        assert configure_utf8_io() is None

    def test_does_not_crash_when_stdout_is_bytes(self):
        orig = sys.stdout
        sys.stdout = io.BytesIO()
        try:
            configure_utf8_io()
        finally:
            sys.stdout = orig

    def test_does_not_crash_when_stdout_is_none(self):
        orig = sys.stdout
        sys.stdout = None
        try:
            configure_utf8_io()
        finally:
            sys.stdout = orig

    def test_does_not_crash_when_stderr_is_none(self):
        orig = sys.stderr
        sys.stderr = None
        try:
            configure_utf8_io()
        finally:
            sys.stderr = orig

    def test_idempotent(self):
        assert configure_utf8_io() is None
        assert configure_utf8_io() is None


def test_cp1252_file_is_decoded_not_mangled(tmp_path):
    """errors="replace" was applied immediately, so a cp1252 file — Word's default on Windows —
    silently became mojibake: every smart quote and em-dash turned into U+FFFD BEFORE scoring.
    Those are exactly the characters an AI-tells scorer cares about."""
    from untell.scripts.io_utils import read_file

    p = tmp_path / "word.txt"
    p.write_bytes("He said \u201chello\u201d \u2014 done.".encode("cp1252"))

    out = read_file(str(p))
    assert "\ufffd" not in out
    assert [hex(ord(c)) for c in out if ord(c) > 127] == ["0x201c", "0x201d", "0x2014"]


def test_utf8_still_preferred(tmp_path):
    from untell.scripts.io_utils import read_file

    p = tmp_path / "u.txt"
    p.write_text("caf\u00e9 \u2014 na\u00efve", encoding="utf-8")
    assert read_file(str(p)) == "caf\u00e9 \u2014 na\u00efve"


def test_utf8_bom_is_stripped(tmp_path):
    from untell.scripts.io_utils import read_file

    p = tmp_path / "bom.txt"
    p.write_bytes(b"\xef\xbb\xbfhello")
    assert read_file(str(p)) == "hello"


def test_scanned_pdf_raises_instead_of_returning_empty(monkeypatch, tmp_path):
    """Every page yielding nothing means a scanned/image PDF. Returning "" handed an empty string to
    the scorer, which would report it as perfectly clean text."""
    import pytest

    import untell.scripts.io_utils as io

    class _Page:
        def extract_text(self):
            return ""

    class _Reader:
        def __init__(self, path):
            self.pages = [_Page(), _Page()]

    monkeypatch.setitem(__import__("sys").modules, "pypdf", type("m", (), {"PdfReader": _Reader}))
    p = tmp_path / "scan.pdf"
    p.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError, match="scanned"):
        io.read_file(str(p))


def test_partially_extractable_pdf_warns_but_returns_text(monkeypatch, tmp_path, caplog):
    import untell.scripts.io_utils as io

    class _Page:
        def __init__(self, t):
            self._t = t

        def extract_text(self):
            return self._t

    class _Reader:
        def __init__(self, path):
            self.pages = [_Page("real text here"), _Page("")]

    monkeypatch.setitem(__import__("sys").modules, "pypdf", type("m", (), {"PdfReader": _Reader}))
    p = tmp_path / "part.pdf"
    p.write_bytes(b"%PDF-1.4")
    with caplog.at_level("WARNING"):
        out = io.read_file(str(p))
    assert "real text here" in out
    assert "PARTIAL" in caplog.text
