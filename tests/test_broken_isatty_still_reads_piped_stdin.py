"""A stream whose isatty raises must still be read as piped input.

io_utils.py:290: when sys.stdin.isatty() raises (replaced/closed stream in a
test harness), the fallback interactive=False means "treat it as non-
interactive so piped input still reaches the command" — per the comment. The
mutation False -> True makes the command return None (no input), silently
dropping piped content.
"""
import sys

from untell.scripts.io_utils import read_stdin_or_none


class _BrokenStdin:
    def isatty(self):
        raise OSError("closed stream")

    def read(self):
        return "piped content"


def test_broken_isatty_still_reads_piped_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", _BrokenStdin())
    assert read_stdin_or_none() == "piped content"
