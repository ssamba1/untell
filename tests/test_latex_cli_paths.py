"""`untell-latex` CLI paths the pure-function tests do not reach: exit codes for
missing files, the --prose shortcut, and the unresolved/lost citation reports."""

from __future__ import annotations

from untell.scripts.latex import main

TEX = (
    "\\documentclass{article}\n"
    "\\begin{document}\n"
    "The effect was significant \\citep{smith2020}.\n"
    "\\end{document}\n"
)

BIB = "@article{smith2020,\n  author = {Smith, A.},\n  title = {A title},\n}\n"


def test_missing_tex_file_exits_two(capsys, tmp_path) -> None:
    assert main([str(tmp_path / "nope.tex")]) == 2
    assert "no such file" in capsys.readouterr().err


def test_prose_shortcut_prints_the_extracted_prose(capsys, tmp_path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text(TEX, encoding="utf-8")
    assert main([str(tex), "--prose"]) == 0
    out = capsys.readouterr().out
    assert "significant" in out
    assert "\\citep" not in out  # markup is dropped, prose is kept


def test_unresolved_citations_exit_one(capsys, tmp_path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text(TEX, encoding="utf-8")
    bib = tmp_path / "refs.bib"
    bib.write_text(BIB, encoding="utf-8")
    # TEX cites smith2020, and the .bib defines it — so make the cite undefined first.
    tex.write_text(TEX.replace("smith2020", "nokey2020"), encoding="utf-8")
    assert main([str(tex), "--bib", str(bib)]) == 1
    assert "UNRESOLVED" in capsys.readouterr().out


def test_resolved_citations_exit_zero(capsys, tmp_path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text(TEX, encoding="utf-8")
    bib = tmp_path / "refs.bib"
    bib.write_text(BIB, encoding="utf-8")
    assert main([str(tex), "--bib", str(bib)]) == 0
    assert "every cited key is defined" in capsys.readouterr().out


def test_lost_citations_exit_one(capsys, tmp_path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text(TEX, encoding="utf-8")
    dropped = tmp_path / "dropped.tex"
    dropped.write_text(TEX.replace("\\citep{smith2020}", ""), encoding="utf-8")
    assert main([str(tex), "--against", str(dropped)]) == 1
    assert "CITATIONS LOST" in capsys.readouterr().out


def test_against_keeping_every_citation_exits_zero(capsys, tmp_path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text(TEX, encoding="utf-8")
    kept = tmp_path / "kept.tex"
    kept.write_text(TEX, encoding="utf-8")
    assert main([str(tex), "--against", str(kept)]) == 0
    assert "keeps every citation" in capsys.readouterr().out


def test_missing_bib_file_exits_two(capsys, tmp_path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text(TEX, encoding="utf-8")
    assert main([str(tex), "--bib", str(tmp_path / "nope.bib")]) == 2
    assert "no such file" in capsys.readouterr().err


def test_missing_against_file_exits_two(capsys, tmp_path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text(TEX, encoding="utf-8")
    assert main([str(tex), "--against", str(tmp_path / "nope.tex")]) == 2
    assert "no such file" in capsys.readouterr().err
