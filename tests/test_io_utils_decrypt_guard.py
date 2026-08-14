"""Killing test: io_utils PDF decryption guard uses `or`, not `and` (line 138).

A password-protected PDF raises an exception whose CLASS name contains "Decrypt"
(pypdf's PdfReadError for encrypted files) but whose message may not contain
"decrypted" (or vice versa). The guard must fire when EITHER matches.
"""
import sys
import pytest

import untell.scripts.io_utils as io


def _install_reader(monkeypatch, exc):
    class _Reader:
        def __init__(self, path):
            raise exc()

    monkeypatch.setitem(sys.modules, "pypdf", type("m", (), {"PdfReader": _Reader}))


def test_exception_class_name_alone_triggers_password_message(monkeypatch, tmp_path):
    """'Decrypt' in class name, but no 'decrypted' in the message."""
    class _DecryptError(Exception):
        pass

    _install_reader(monkeypatch, _DecryptError)
    p = tmp_path / "locked.pdf"
    p.write_bytes(b"%PDF-1.4" + b"x" * 200)  # non-empty so the empty check passes

    with pytest.raises(ValueError, match="password-protected"):
        io.read_file(str(p))


def test_message_alone_triggers_password_message(monkeypatch, tmp_path):
    """'decrypted' in the message, but the class name has no 'Decrypt'."""
    class _WeirdError(Exception):
        def __str__(self):
            return "file must be decrypted first"

    _install_reader(monkeypatch, _WeirdError)
    p = tmp_path / "locked2.pdf"
    p.write_bytes(b"%PDF-1.4" + b"x" * 200)

    with pytest.raises(ValueError, match="password-protected"):
        io.read_file(str(p))
