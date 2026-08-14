"""The scrub CLI's JSON is ASCII-safe: non-ASCII input must be escaped, not literal.

scrub.py:119 `ensure_ascii=True`. The mutation -> False emits literal non-ASCII
characters, which would crash a cp1252 (Windows) stdout — the exact portability
failure the flag exists to prevent. A test asserting the JSON output is pure
ASCII distinguishes the mutation (it survived 8 prior audits under the wrong
assumption that "tests don't check stdout encoding" — they didn't, until now).
"""
import json

from untell.scripts.scrub import main as scrub_main


def test_scrub_cli_json_is_ascii_safe(monkeypatch, capsys):
    # Non-ASCII input (café + ZWSP watermark) through the --json path.
    text = "caf\u00e9 \u200b r\u00e9sum\u00e9"
    rc = scrub_main(["--json", text])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # must not raise — the ensure_ascii flag's whole point
    parsed = json.loads(out)
    assert parsed["hidden_before"] == 1
    assert parsed["hidden_after"] == 0
    # The JSON-level value is the unescaped text; the WIRE format is ASCII.
    assert parsed["text"] == "caf\u00e9  r\u00e9sum\u00e9"
