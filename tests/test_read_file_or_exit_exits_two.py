"""read_file_or_exit exits 2 (usage error), not 3.

io_utils.py:264/267: a missing/unreadable file raises SystemExit(2), matching
argparse's usage-error convention. The mutation 2 -> 3 changes the exit code;
callers distinguishing usage errors (2) from other failures would misread it.
The docstring explicitly states exit 2 is the convention, so the exact code is
part of the contract.
"""
import os
import tempfile

import pytest

from untell.scripts.io_utils import read_file_or_exit


def test_missing_file_exits_two():
    path = os.path.join(tempfile.mkdtemp(), "definitely-not-here.txt")
    with pytest.raises(SystemExit) as exc:
        read_file_or_exit(path)
    assert exc.value.code == 2


def test_unanticipated_oserror_exits_two(monkeypatch):
    def boom(_path):
        raise OSError("device not ready")

    monkeypatch.setattr("untell.scripts.io_utils.read_file", boom)
    with pytest.raises(SystemExit) as exc:
        read_file_or_exit("whatever")
    assert exc.value.code == 2

