"""No input (interactive terminal) exits 2, not 3.

verify.py:364: when stdin is a terminal (read_stdin_or_none returns None), the
command prints the usage error and exits 2 — same code as "nothing ran". The
mutation 2 -> 3 changes the no-input exit code; a caller distinguishing 1
(checked-and-failed) from 2 (nothing ran) would misread 3 as something else.
Pinned with read_stdin_or_none patched to simulate a TTY.
"""
from unittest.mock import patch

from untell.scripts.verify import main


def test_no_input_terminates_with_usage_error_and_two():
    with patch("untell.scripts.io_utils.read_stdin_or_none", return_value=None):
        assert main([]) == 2
