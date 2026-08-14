"""Empty input exits 2 (config problem), not 3 or 1.

verify.py:368: whitespace-only text returns 2 — the same code as "no checkers
configured". The mutation 2 -> 3 changes the exit code for whitespace input,
and a caller distinguishing 1 (checked-and-failed) from 2 (nothing ran) would
misread 3. The no-results path (line 400) is already pinned by the commercial
test; this pins the empty-input path.
"""
import contextlib
import io
import json

from untell.scripts.verify import main


def test_whitespace_input_exits_two():
    assert main(["   "]) == 2


def test_whitespace_input_reports_empty():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["   "])
    assert rc == 2
    assert json.loads(buf.getvalue())["error"] == "empty input"
