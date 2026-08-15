"""The quality CLI escapes non-ASCII in its JSON (portable stdout).

quality.py:320: `json.dumps(..., ensure_ascii=True)` — a non-UTF-8 stdout (e.g.
Windows cp1252) must never crash on the emitted text; non-ASCII is escaped as
\\uXXXX. The mutation True -> False emits literal non-ASCII. Pinned with a
patched method() that returns a non-ASCII value.
"""
import io
import sys
from unittest.mock import patch

from untell.scripts.quality import main


def test_cli_json_is_ascii_safe(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    with patch("untell.scripts.quality.method", return_value="héllo"):
        rc = main(["a", "b"])
    out = buf.getvalue()
    assert rc == 0
    assert "\\u00e9" in out, f"expected escaped non-ASCII in {out!r}"
    assert not any(ord(c) > 127 for c in out), "output must stay ASCII-safe"
