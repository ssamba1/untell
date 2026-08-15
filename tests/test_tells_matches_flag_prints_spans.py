"""The CLI tells --matches flag must print the matched substrings in plain output.

The flag's help says "include the matched substrings" and the result dict always
carried them (--json showed them), but the plain renderer ignored them, so
`untell tells --matches <text>` printed byte-identical output to the no-flag call —
a silent no-op in the default rendering mode.
"""

from __future__ import annotations

from untell.scripts.tells import main

TEXT = (
    "In conclusion, it is important to note that moreover the framework "
    "showcases a robust solution. Additionally, it boasts remarkable versatility."
)
# Measured span set for TEXT (pass 911 probe): cliche "it is important to note" /
# "In conclusion", formulaic_transition "Additionally", ai_vocab "remarkable" /
# "robust" / "boasts".
SPANS = ("In conclusion", "it is important to note", "Additionally", "robust", "boasts")


def test_matches_flag_prints_the_matched_spans_in_plain_output(capsys):
    rc = main(["--matches", TEXT])
    out = capsys.readouterr().out
    assert rc == 0
    for span in SPANS:
        assert span in out, f"matched span {span!r} missing from --matches output"


def test_without_flag_plain_output_has_no_matched_spans(capsys):
    rc = main([TEXT])
    out = capsys.readouterr().out
    assert rc == 0
    assert "matched spans" not in out
    for span in SPANS:
        assert span not in out, f"span {span!r} printed without --matches"
