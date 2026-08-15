"""The scrub CLI — the piece that let SKILL.md reach the watermark scrub at all.

`scrub_hidden` has always existed in `untell.attacks.unicode_tricks`, and the MCP server exposed
it, but there was no command-line entry point. SKILL.md drives every step through
`python scripts/<name>.py`, so the flagship path never scrubbed: text could go through the entire
loop, come out reading perfectly human, and still carry an intact zero-width watermark.
"""

from __future__ import annotations

import json

import pytest

from untell.attacks.unicode_tricks import count_hidden
from untell.scripts import scrub

DIRTY = "The​ result was⁠ clear.‍"
CLEAN = "The result was clear."


def test_json_mode_reports_counts_and_cleans(capsys):
    assert scrub.main(["--json", DIRTY]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hidden_before"] == count_hidden(DIRTY) > 0
    assert payload["hidden_after"] == 0
    assert payload["changed"] is True
    assert payload["text"] == CLEAN


def test_bare_mode_puts_only_text_on_stdout(capsys):
    """stdout must stay pipeable — the removal notice belongs on stderr."""
    assert scrub.main([DIRTY]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == CLEAN
    assert "hidden character" in captured.err


def test_clean_text_is_unchanged_and_still_exits_zero(capsys):
    """"Nothing to remove" is a successful scrub; a non-zero code would break `scrub && next`."""
    assert scrub.main(["Plain clean text."]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "Plain clean text."
    assert captured.err == ""


def test_json_mode_on_clean_text_reports_unchanged(capsys):
    assert scrub.main(["--json", "Plain clean text."]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "hidden_before": 0,
        "hidden_after": 0,
        "changed": False,
        "text": "Plain clean text.",
    }


def test_missing_file_is_a_usage_error_not_a_traceback(capsys):
    """An uncaught FileNotFoundError tells a script caller nothing it can act on."""
    assert scrub.main(["--file", "definitely_not_a_real_file.txt"]) == 2


def test_reads_from_file(tmp_path, capsys):
    p = tmp_path / "in.txt"
    p.write_text(DIRTY, encoding="utf-8")
    assert scrub.main(["--json", "--file", str(p)]) == 0
    assert json.loads(capsys.readouterr().out)["text"] == CLEAN


def test_no_input_at_all_is_a_usage_error(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert scrub.main([]) == 2


@pytest.mark.parametrize(
    "text",
    ["", "Ordinary sentence.", "Numbers 42 and 3.14 stay.", "Café naïve résumé — em dash."],
    ids=["empty", "plain", "numbers", "accents-and-emdash"],
)
def test_visible_text_is_never_altered(text, capsys):
    """The scrub must remove only invisible carriers. Mangling accents or punctuation here would
    silently corrupt every document that passes through the skill."""
    scrub.main(["--json", text])
    assert json.loads(capsys.readouterr().out)["text"] == text


def test_help_names_the_untell_command(capsys):
    """The usage line advertised the program as `scrub.py` even when invoked as `untell scrub`
    (or `untell-scrub`) — the name a user would type back, which does not exist on PATH. Every
    other subcommand names itself `untell-<name>`; this one must match."""
    with pytest.raises(SystemExit) as exc:
        scrub.main(["--help"])
    assert exc.value.code == 0
    assert "usage: untell-scrub" in capsys.readouterr().out
