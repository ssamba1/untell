"""`untell-voice` CLI: the table renderer must surface the thin-sample warning.

`voice_report` carries the warning as a key and the JSON path prints it verbatim; the
table path had a separate print of its own that the existing CLI tests never reached
(they use a sample long enough to silence the warning)."""

from __future__ import annotations

from untell.scripts.voice import main

DRAFT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale "
    "and significantly improves overall efficiency across the evaluated corpus."
)


def test_thin_sample_warning_reaches_the_table(capsys, tmp_path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("short sample", encoding="utf-8")  # 2 words < MIN_SAMPLE_WORDS
    draft = tmp_path / "draft.txt"
    draft.write_text(DRAFT, encoding="utf-8")
    assert main(["--sample", str(sample), "--draft", str(draft)]) == 0
    out = capsys.readouterr().out
    assert "WARNING:" in out
    assert "below 150" in out


def test_full_sample_table_has_no_warning(capsys, tmp_path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("I write in short sentences. " * 50, encoding="utf-8")
    draft = tmp_path / "draft.txt"
    draft.write_text(DRAFT, encoding="utf-8")
    assert main(["--sample", str(sample), "--draft", str(draft)]) == 0
    out = capsys.readouterr().out
    assert "WARNING:" not in out
    assert "voice distance:" in out
