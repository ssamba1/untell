"""`--file` on a broken .docx or .pdf printed a traceback and exited 1.

Both readers already convert a MISSING DEPENDENCY into a `ValueError`, which `read_file_or_exit`
turns into `error: ...` and exit 2 — the convention here for a configuration problem. Neither
converted the parsing libraries' OWN errors. `docx.opc.exceptions.PackageNotFoundError` and every
`pypdf.errors.*` descend from their own base classes, not from `ValueError` or `OSError`, so they
escaped both handlers.

MEASURED before, via `untell tells --file`:

    zero.pdf       exit 1  traceback  pypdf.errors.EmptyFileError: Cannot read an empty file
    corrupt.pdf    exit 1  traceback  pypdf.errors.PdfStreamError: Stream has ended unexpectedly
    encrypted.pdf  exit 1  traceback  pypdf.errors.FileNotDecryptedError: File has not been decrypted
    zero.docx      exit 1  traceback  PackageNotFoundError: Package not found at '...'
    text.docx      exit 1  traceback  PackageNotFoundError: Package not found at '...'

"Package not found" is the actively misleading one: the file is right there and readable, it simply
is not a .docx.

After, every case is exit 2 with one line and no traceback, and the three situations are told apart
because they need different actions — empty, unreadable, or password-protected.

ONE THING THIS GOT WRONG FIRST. Guarding only `PdfReader(path)` left the encrypted case still
exiting 1: constructing the reader succeeds on an encrypted file and `.pages` returns a list; the
refusal surfaces only when a page is actually read. The guard has to span extraction too, which is
why `texts = [...]` sits inside the `try`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _run(path: Path) -> tuple[int, str]:
    import os

    env = {**os.environ, "UNTELL_LITE_NO_TORCH": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "untell.scripts.tells", "--file", str(path)],
        capture_output=True, text=True, env=env, cwd=str(_ROOT), timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


@pytest.fixture(scope="module")
def broken(tmp_path_factory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("broken-docs")
    files = {
        "zero.pdf": b"",
        "corrupt.pdf": b"\x89PNG\r\n\x1a\n",
        "zero.docx": b"",
        "text.docx": b"this is plain text, not a zip\n",
    }
    out = {}
    for name, payload in files.items():
        p = d / name
        p.write_bytes(payload)
        out[name] = p
    return out


@pytest.mark.parametrize("name", ["zero.pdf", "corrupt.pdf", "zero.docx", "text.docx"])
def test_a_broken_document_exits_two_with_one_line(name: str, broken) -> None:
    pytest.importorskip("pypdf" if name.endswith(".pdf") else "docx")
    code, output = _run(broken[name])

    assert "Traceback" not in output, f"{name} printed a traceback:\n{output[-400:]}"
    assert code == 2, f"{name} exited {code}, expected 2 (configuration problem)"
    assert "error:" in output, f"{name} produced no error line: {output[-200:]!r}"


@pytest.mark.parametrize("name", ["zero.pdf", "zero.docx"])
def test_an_empty_file_is_named_as_empty(name: str, broken) -> None:
    """Empty and corrupt need different sentences. "may be corrupt" sends the reader looking for
    damage that is not there."""
    pytest.importorskip("pypdf" if name.endswith(".pdf") else "docx")
    _code, output = _run(broken[name])
    assert "is empty" in output, f"{name}: {output[-200:]!r}"


@pytest.mark.parametrize("name", ["corrupt.pdf", "text.docx"])
def test_a_wrong_format_says_so(name: str, broken) -> None:
    pytest.importorskip("pypdf" if name.endswith(".pdf") else "docx")
    _code, output = _run(broken[name])
    assert "not a readable" in output, f"{name}: {output[-200:]!r}"
    assert "different format" in output


def test_an_encrypted_pdf_is_told_apart_from_a_broken_one(tmp_path) -> None:
    """The case that stayed broken after the first fix. A valid, password-protected file needs a
    password, which is a different action from "your file is damaged"."""
    pypdf = pytest.importorskip("pypdf")

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    target = tmp_path / "encrypted.pdf"
    with open(target, "wb") as handle:
        writer.write(handle)

    code, output = _run(target)
    assert "Traceback" not in output, output[-400:]
    assert code == 2
    assert "password-protected" in output, f"not identified as encrypted: {output[-250:]!r}"
    assert "qpdf" in output, "no remedy offered"


def test_a_valid_document_still_reads(tmp_path) -> None:
    """Guards every case above. A reader that rejected everything would satisfy them all."""
    docx = pytest.importorskip("docx")

    document = docx.Document()
    document.add_paragraph(
        "Moreover, the framework leverages robust methodologies to deliver outcomes."
    )
    target = tmp_path / "good.docx"
    document.save(target)

    code, output = _run(target)
    assert code == 0, f"a valid .docx failed: {output[-300:]}"
    assert "AI-tells" in output
