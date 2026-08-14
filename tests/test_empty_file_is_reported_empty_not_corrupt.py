"""An empty file is reported as empty, not as corrupt.

io_utils.py:50 `os.path.getsize(path) > 0` distinguishes an empty file (0 bytes,
False) from a corrupt one (True). The mutation > -> >= makes every file "has
bytes", so an empty .docx is reported as "not a readable .docx (corrupt...)"
instead of "is empty, so there is no .docx to read". This test pins the
boundary — 0 bytes must be "empty", not "corrupt".
"""
import os
import tempfile

from untell.scripts.io_utils import read_file


def test_empty_docx_reports_empty_not_corrupt():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "empty.docx")
        open(path, "wb").close()
        try:
            read_file(path)
        except ValueError as exc:
            assert "is empty" in str(exc), str(exc)
            assert "corrupt" not in str(exc), str(exc)
        else:
            raise AssertionError("empty .docx should raise ValueError")
