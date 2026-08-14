"""The sentences CLI's JSON is ASCII-safe: non-ASCII input must be escaped.

sentences.py:338 `ensure_ascii=True`. The mutation -> False emits literal
non-ASCII characters, which would crash a cp1252 (Windows) stdout — the same
portability class as scrub.py:119 and quality.py:304, both killed this way.
"""
import json

from untell.scripts.sentences import main as sentences_main


def test_sentences_cli_json_is_ascii_safe(monkeypatch, capsys):
    text = "caf\u00e9 and r\u00e9sum\u00e9 text here"
    rc = sentences_main(["--json", text])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # must not raise — the ensure_ascii flag's whole point
    parsed = json.loads(out)
    assert "sentences" in parsed
