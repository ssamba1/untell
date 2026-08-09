"""Tests for io_utils — UTF-8 configuration and stdin helpers."""
from __future__ import annotations

import io
import sys

import pytest

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


# --- encoding coverage --------------------------------------------------------------------------
# `latin-1` is last in _TEXT_ENCODINGS and maps all 256 byte values, so it CANNOT raise
# UnicodeDecodeError — the decode loop always "succeeded" there. That made the lossy-replacement
# branch unreachable and, far worse, silently turned UTF-16 (what Windows "Save as -> Unicode"
# writes) into mojibake:
#     'The "smart quotes"'  ->  'ÿþT\x00h\x00e\x00 \x00"\x00s\x00m\x00a\x00r\x00t\x00...'
# which was then scored and rewritten as if it were the user's prose.

_SAMPLE = 'The "smart quotes" — and an em-dash — cost €5 in café Zürich.'
_CP1252_SAMPLE = 'The "smart quotes" — and an em-dash — cost E5 in café Zürich.'

ENCODING_CASES = [
    ("utf-8", _SAMPLE.encode("utf-8"), _SAMPLE),
    ("utf-8-sig", _SAMPLE.encode("utf-8-sig"), _SAMPLE),
    ("cp1252", _CP1252_SAMPLE.encode("cp1252"), _CP1252_SAMPLE),
    ("utf-16-le-bom", _SAMPLE.encode("utf-16"), _SAMPLE),
    ("utf-16-be-bom", b"\xfe\xff" + _SAMPLE.encode("utf-16-be"), _SAMPLE),
    ("utf-32-bom", _SAMPLE.encode("utf-32"), _SAMPLE),
    ("latin-1", "café".encode("latin-1"), "café"),
    ("empty", b"", ""),
]


@pytest.mark.parametrize("label,raw,expected", ENCODING_CASES, ids=[c[0] for c in ENCODING_CASES])
def test_text_files_round_trip_regardless_of_encoding(tmp_path, label, raw, expected):
    from untell.scripts.io_utils import read_file

    path = tmp_path / f"{label}.txt"
    path.write_bytes(raw)
    assert read_file(str(path)) == expected


@pytest.mark.parametrize(
    "label,raw",
    [
        ("all byte values", bytes(range(256)) * 2),
        ("png header", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"),
        ("utf-16 without bom", "hello there".encode("utf-16-le")),
    ],
)
def test_binary_input_raises_instead_of_scoring_garbage(tmp_path, label, raw):
    """latin-1 accepts any byte, so a binary file read back as a string and the detector would
    happily report a number for it. Real text contains no NUL; returning garbage is worse than
    failing, which is the same call this module already makes for a scanned PDF."""
    from untell.scripts.io_utils import read_file

    path = tmp_path / "binary.bin"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="NUL"):
        read_file(str(path))


def test_latin1_fallback_is_announced(tmp_path, caplog):
    """Arriving at latin-1 is not evidence the result is right — it is where every stricter codec
    already failed, and latin-1 cannot fail. Say so rather than returning it silently."""
    import logging

    from untell.scripts.io_utils import read_file

    path = tmp_path / "undecodable.txt"
    path.write_bytes(b"caf\xe9 \x81\x8d\x8f")  # 0x81/0x8d/0x8f are undefined in cp1252
    with caplog.at_level(logging.WARNING, logger="untell.scripts.io_utils"):
        read_file(str(path))
    assert any("latin-1" in r.getMessage() for r in caplog.records), "fell back silently"


class TestEveryFileEntryPointDecodesProperly:
    """`read_file()` existed and only two callers used it.

    It sniffs BOMs, falls back through UTF-16/cp1252/latin-1, handles docx/pdf and rejects
    binaries. run.py and tells.py used it; score, verify, sentences, humanness and scrub each did
    `open(encoding="utf-8", errors="replace")` instead, which does not fail on a UTF-16 file — it
    silently substitutes U+FFFD:

        naive     '\ufffd\ufffdL\x00e\x00 \x00c\x00a\x00f\x00\ufffd\x00 ...'
        read_file 'Le café naïve coûte cinq euros. Résumé attached, per Smith (2024).'

    So `untell score --file` on a UTF-16 document scored garbage and reported it as a real number.
    This is the same defect already fixed once in run.py; it stayed open everywhere else.
    """

    SAMPLE = "Le caf\u00e9 na\u00efve co\u00fbte cinq euros. R\u00e9sum\u00e9 attached, per Smith (2024)."

    @pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "cp1252", "latin-1"])
    def test_read_file_round_trips_every_common_encoding(self, tmp_path, encoding):
        from untell.scripts.io_utils import read_file

        p = tmp_path / f"doc_{encoding}.txt"
        p.write_bytes(self.SAMPLE.encode(encoding))
        assert read_file(str(p)).strip() == self.SAMPLE

    @pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
    def test_bomless_utf16_is_rejected_loudly_not_mangled(self, tmp_path, encoding):
        """BOM-less UTF-16 is genuinely ambiguous — there is nothing to sniff, and the bytes look
        like ASCII interleaved with NULs.

        `read_file` raises rather than guessing, which is the right call: the failure mode this
        whole class of bug is about is SILENT corruption, and a loud error is the opposite of that.
        Asserted explicitly so nobody "improves" it into a silent best-effort decode.
        """
        from untell.scripts.io_utils import read_file

        p = tmp_path / f"doc_{encoding}.txt"
        p.write_bytes(self.SAMPLE.encode(encoding))
        with pytest.raises(ValueError):
            read_file(str(p))

    def test_no_cli_reads_a_file_with_a_naive_open(self):
        """Pins the fix at every entry point rather than one at a time.

        Matching on source is deliberate: a behavioural test needs a real model per CLI, while the
        defect is purely "which reader did this call", which is visible statically and cannot drift.
        """
        import re
        from pathlib import Path

        repo = Path(__file__).resolve().parent.parent
        offenders = []
        for rel in ("untell/scripts/score.py", "untell/scripts/verify.py",
                    "untell/scripts/sentences.py", "untell/scripts/tells.py",
                    "untell/scripts/scrub.py", "untell/scripts/run.py", "untell/humanness.py"):
            src = (repo / rel).read_text(encoding="utf-8", errors="replace")
            if not re.search(r'args\.file', src):
                continue
            # `read_file_or_exit` is `read_file` plus a one-line message and exit 2 for the three
            # ordinary path mistakes. Both count: the guarantee this test protects is that the
            # BOM-aware, encoding-sniffing, binary-rejecting reader is the one being used, not
            # which of its two entry points a given CLI prefers.
            if "read_file(" not in src and "read_file_or_exit(" not in src:
                offenders.append(rel)
        assert not offenders, (
            f"these read --file without going through read_file/read_file_or_exit: {offenders}"
        )


class TestAMissingOptionalReaderNamesTheExtra:
    """`--file report.docx` without python-docx raised `ModuleNotFoundError: No module named
    'docx'`.

    That is the first thing a user with a Word document tries, and the message does not name
    anything they can install: the import is `docx` and the package is `python-docx`. Nothing in
    the error connects either to the `untell[docs]` extra that provides it.

    Found by auditing which optional extras CI installs — the same audit that found the BERTScore
    gate rejecting 95% of good rewrites. An extra no environment exercises is a code path a user
    can reach with one pip flag and nobody has run.
    """

    @staticmethod
    def _without(*blocked):
        """Context manager making the named modules unimportable, as a fresh install has them."""
        import builtins
        import contextlib

        @contextlib.contextmanager
        def ctx():
            real = builtins.__import__

            def guard(name, *a, **k):
                if name in blocked:
                    raise ModuleNotFoundError(f"No module named '{name}'")
                return real(name, *a, **k)

            builtins.__import__ = guard
            try:
                yield
            finally:
                builtins.__import__ = real

        return ctx()

    @pytest.mark.parametrize(
        "suffix,module,package",
        [("docx", "docx", "python-docx"), ("pdf", "pypdf", "pypdf")],
    )
    def test_the_message_names_the_package_and_the_extra(self, suffix, module, package, tmp_path):
        from untell.scripts.io_utils import read_file

        probe = tmp_path / f"probe.{suffix}"
        probe.write_bytes(b"stub")
        with self._without(module):
            with pytest.raises(ValueError) as exc:
                read_file(str(probe))
        message = str(exc.value)
        assert package in message, f"does not name the package to install: {message}"
        assert "untell[docs]" in message, f"does not name the extra: {message}"
        assert "No module named" not in message, "raw ImportError text leaked through"

    def test_a_plain_text_file_is_unaffected_by_the_guards(self, tmp_path):
        """The guards must fire only for the formats that need the extra."""
        from untell.scripts.io_utils import read_file

        probe = tmp_path / "plain.txt"
        probe.write_text("Ordinary text.", encoding="utf-8")
        with self._without("docx", "pypdf"):
            assert read_file(str(probe)) == "Ordinary text."
