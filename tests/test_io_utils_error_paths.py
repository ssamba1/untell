"""io_utils branches the file-level tests do not reach: the corrupt/empty docx and
pdf refusal paths, the BOM-but-undecodable fallthrough, the directory and
permission refusals, and the stdin failure modes."""

from __future__ import annotations

import logging
import os

import pytest

from untell.scripts import io_utils


class _FakeStdin:
    def __init__(self, isatty_result, read_result=None, read_error=None):
        self._isatty = isatty_result
        self._read_result = read_result
        self._read_error = read_error

    def isatty(self):
        if isinstance(self._isatty, Exception):
            raise self._isatty
        return self._isatty

    def read(self):
        if self._read_error is not None:
            raise self._read_error
        return self._read_result


def test_has_bytes_returns_true_when_size_is_unreadable(monkeypatch) -> None:
    def boom(path):
        raise OSError("size unreadable")

    monkeypatch.setattr(os.path, "getsize", boom)
    assert io_utils._has_bytes("anything") is True


def test_empty_docx_is_reported_empty(monkeypatch) -> None:
    monkeypatch.setattr(io_utils, "_has_bytes", lambda path: False)

    class PkgNotFound(Exception):
        pass

    import docx

    monkeypatch.setattr(docx, "Document", lambda path: (_ for _ in ()).throw(PkgNotFound("nope")))
    with pytest.raises(ValueError, match="is empty"):
        io_utils._read_docx("zero.docx")


def test_corrupt_docx_is_reported_as_unreadable(monkeypatch) -> None:
    monkeypatch.setattr(io_utils, "_has_bytes", lambda path: True)

    class PkgNotFound(Exception):
        pass

    import docx

    monkeypatch.setattr(docx, "Document", lambda path: (_ for _ in ()).throw(PkgNotFound("nope")))
    with pytest.raises(ValueError, match="not a readable .docx"):
        io_utils._read_docx("broken.docx")


def test_empty_pdf_is_reported_empty(monkeypatch) -> None:
    monkeypatch.setattr(io_utils, "_has_bytes", lambda path: False)
    import pypdf

    monkeypatch.setattr(pypdf, "PdfReader", lambda path: (_ for _ in ()).throw(RuntimeError("empty")))
    with pytest.raises(ValueError, match="is empty"):
        io_utils._read_pdf("zero.pdf")


def test_encrypted_pdf_names_the_password(monkeypatch) -> None:
    monkeypatch.setattr(io_utils, "_has_bytes", lambda path: True)
    import pypdf

    class NotDecrypted(Exception):
        pass

    monkeypatch.setattr(pypdf, "PdfReader", lambda path: (_ for _ in ()).throw(NotDecrypted("file has not been decrypted")))
    with pytest.raises(ValueError, match="password-protected"):
        io_utils._read_pdf("locked.pdf")


def test_corrupt_pdf_is_reported_as_unreadable(monkeypatch) -> None:
    monkeypatch.setattr(io_utils, "_has_bytes", lambda path: True)
    import pypdf

    class StreamEnded(Exception):
        pass

    monkeypatch.setattr(pypdf, "PdfReader", lambda path: (_ for _ in ()).throw(StreamEnded("stream ended")))
    with pytest.raises(ValueError, match="not a readable .pdf"):
        io_utils._read_pdf("broken.pdf")


def test_a_bom_that_does_not_decode_falls_through_to_latin1(tmp_path, caplog) -> None:
    """A UTF-16 BOM over a body that is not valid UTF-16 must not silently win."""
    p = tmp_path / "odd.txt"
    # UTF-16-LE BOM + one byte that even cp1252 cannot map (0x81 is undefined there):
    # the body cannot decode as UTF-16, so the BOM guess must not silently win.
    p.write_bytes(b"\xff\xfe\x81")
    with caplog.at_level(logging.WARNING, logger="untell.scripts.io_utils"):
        text = io_utils._read_text(str(p))
    assert "latin-1" in caplog.text
    assert text  # something came back, with the caveat attached


def test_read_file_refuses_a_directory(tmp_path) -> None:
    with pytest.raises(ValueError, match="is a directory"):
        io_utils.read_file(str(tmp_path))


def test_read_file_refuses_when_unreadable(tmp_path, monkeypatch) -> None:
    p = tmp_path / "secret.txt"
    p.write_text("hi", encoding="utf-8")
    monkeypatch.setattr(os, "access", lambda path, mode: False)
    with pytest.raises(ValueError, match="permission denied"):
        io_utils.read_file(str(p))


def test_stdin_isatty_raising_still_reads(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", _FakeStdin(ValueError("no isatty"), read_result="piped text"))
    assert io_utils.read_stdin_or_none() == "piped text"


def test_stdin_undecodable_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.stdin", _FakeStdin(False, read_error=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"))
    )
    assert io_utils.read_stdin_or_none() is None


def test_stdin_is_interactive_returns_none(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", _FakeStdin(True, read_result="should not be read"))
    assert io_utils.read_stdin_or_none() is None
