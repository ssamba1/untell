"""voice CLI requires --sample (missing it is a usage error, not a crash).

voice.py:253: `p.add_argument("--sample", required=True, ...)`. The mutation
True -> False makes --sample optional; calling main(['--draft', PATH]) then
reaches read_file_or_exit(None) and raises TypeError (os.path.exists(None)),
instead of the clean SystemExit(2) usage error. The required guard is what
keeps the CLI's contract.
"""
import os
import tempfile

import pytest

from untell.scripts.voice import main


def test_missing_sample_is_usage_error():
    d = tempfile.mkdtemp()
    draft = os.path.join(d, "draft.txt")
    with open(draft, "w") as f:
        f.write("some draft text here.")
    with pytest.raises(SystemExit) as exc:
        main(["--draft", draft])
    assert exc.value.code == 2
