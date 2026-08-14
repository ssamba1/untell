"""The preserve CLI's JSON is ASCII-safe: U+27E6 sentinels must stay escaped.

preserve.py:889 `ensure_ascii=True` (with an explicit comment: sentinels must
survive a Windows cp1252 stdout). The mutation -> False emits literal U+27E6,
which would crash cp1252. Same portability class as scrub.py:119,
quality.py:304-adjacent, sentences.py:338 — all killed this way.
"""
import json

from untell.scripts.preserve import main as preserve_main


def test_preserve_cli_json_is_ascii_safe(monkeypatch, capsys):
    # A lockable fact (dotted identifier) produces U+27E6 sentinels in output.
    rc = preserve_main(["The value v1.2.3 was measured."])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # must not raise — the ensure_ascii flag's whole point
    parsed = json.loads(out)
    assert "masked" in parsed and "mapping" in parsed
