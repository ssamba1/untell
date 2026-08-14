"""An unreadable file is not evidence of emptiness.

io_utils.py:52: when os.path.getsize raises, _has_bytes returns True — "unreadable
size is not evidence of emptiness; let the parser's message stand". The mutation
True -> False makes an unreadable file read as empty, sending the reader to the
wrong diagnostic ("there is nothing here" for a file that may be full but
unreadable). Forced with a monkeypatched getsize that raises.
"""
import os

from untell.scripts.io_utils import _has_bytes


def test_unreadable_size_is_not_empty(monkeypatch):
    def boom(_path):
        raise OSError("permission denied")

    monkeypatch.setattr(os.path, "getsize", boom)
    assert _has_bytes("whatever") is True
