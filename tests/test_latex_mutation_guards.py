"""Killing tests for the latex.py mutation survivors (2026-08-14 sweep).

  line 88    boundary: >= -> >     is_latex at exactly 2 signals.
  line 102   constant: 3 -> 4      prose_only unwrap loop bound.
  line 194   constant: 2 -> 3      CLI exit code for missing --bib file.
  line 206   constant: 2 -> 3      CLI exit code for missing --against file.

88, 194 and 206 are killed here. 102 pins the current contract: the unwrap loop
runs three passes (enough for \textbf{\\emph{x}} per the comment); a FOUR-level
nest loses the word — that is the documented bound, and the mutation (four passes)
would silently start keeping depth-4 words, changing the scoring view.
"""

from __future__ import annotations

from untell.scripts.latex import is_latex, main, prose_only

PAPER = r"""\documentclass{article}
\begin{document}
\section{Introduction}
Moreover, it is crucial to note that the method replicates.
\end{document}
"""


class TestIsLatexBoundary:
    """Survivor latex.py:88 — `>= 2` mutated to `> 2`.

    A text with EXACTLY two LaTeX signals is LaTeX. The mutation demands three."""

    def test_two_signals_is_latex(self) -> None:
        # \section{...} (one signal) + \cite{...} (another) = exactly 2
        text = r"\section{Intro} and a \cite{key} in the text."
        assert is_latex(text)

    def test_one_signal_is_not_latex(self) -> None:
        text = r"only a stray \section{Intro} in prose"
        assert not is_latex(text)


class TestProseUnwrapBound:
    """Survivor latex.py:102 — `range(3)` mutated to `range(4)`.

    The unwrap loop is bounded at three passes (comment: nested \\textbf{\\emph{x}}
    needs more than one pass). Depth 3 unwraps fully; depth 4 does not — that is
    the contract the bound documents, and it is what the mutation would change."""

    def test_three_levels_unwrap(self) -> None:
        text = r"\textbf{\emph{\textit{done}}}"
        assert "done" in prose_only(text)

    def test_four_levels_do_not(self) -> None:
        text = r"\textbf{\emph{\textit{\underline{done}}}}"
        assert "done" not in prose_only(text)


class TestCliExitCodes:
    """Survivors latex.py:194/206 — `return 2` mutated to `return 3`.

    A missing --bib or --against file is a usage error with exit code 2."""

    def test_missing_bib_file_exits_2(self, tmp_path, capsys) -> None:
        src = tmp_path / "paper.tex"
        src.write_text(PAPER, encoding="utf-8")
        missing = tmp_path / "nope.bib"
        rc = main([str(src), "--bib", str(missing)])
        assert rc == 2
        assert "no such file" in capsys.readouterr().err

    def test_missing_against_file_exits_2(self, tmp_path, capsys) -> None:
        src = tmp_path / "paper.tex"
        src.write_text(PAPER, encoding="utf-8")
        missing = tmp_path / "nope.tex"
        rc = main([str(src), "--against", str(missing)])
        assert rc == 2
        assert "no such file" in capsys.readouterr().err
