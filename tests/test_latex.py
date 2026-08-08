"""LaTeX: prose extraction for scoring, and citation survival.

Both problems here only appear on real `.tex` input, and both were found by running the tool on a
four-paragraph paper rather than on a paragraph of prose. The academic niche is the one place this
repository claims a specific advantage, and on an actual document the tool was a no-op.
"""

from __future__ import annotations

import pytest

from untell.scripts.latex import (
    LOCKED_ENVIRONMENTS,
    bib_keys,
    cite_keys,
    dropped_citations,
    is_latex,
    prose_only,
    unresolved_citations,
)

PAPER = r"""\documentclass{article}
\begin{document}
\begin{abstract}
We present EdgeFlow, a novel approach \cite{smith2020}.
\end{abstract}

\section{Introduction}
Moreover, it is crucial to underscore the pivotal role of frameworks \cite{lee2019}.
The method achieves $92.4\%$ accuracy on the benchmark.

\begin{theorem}[Convergence]
The iteration converges for all $\alpha > 0$.
\end{theorem}
\end{document}
"""

BIB = """@article{smith2020, title={A paper}, author={Smith, J}, year={2020}}
@inproceedings{lee2019, title={Another}, author={Lee, K}, year={2019}}
"""


class TestTheDocumentEnvironmentIsNotLocked:
    """`latex_env` used to match ANY environment, and `document` is an environment.

    MEASURED on this paper: the whole file masked to `⟦HZ0000⟧\\n⟦HZ0001⟧`, the rewriter received
    nothing, and `untell humanize --file paper.tex` returned the input unchanged. LaTeX support is
    a headline promise of the academic niche and on a real document it did nothing — the mirror
    image of the "LaTeX entirely unprotected" defect it was written to fix.
    """

    def test_body_prose_reaches_the_rewriter(self):
        from untell.scripts.preserve import lock

        masked, _ = lock(PAPER)
        assert "frameworks" in masked, f"body prose was masked away: {masked!r}"

    def test_the_protected_environments_are_still_locked(self):
        from untell.scripts.preserve import lock

        masked, _ = lock(PAPER)
        for forbidden in ("We present EdgeFlow", "The iteration converges"):
            assert forbidden not in masked, f"{forbidden!r} was left rewritable"

    def test_locking_still_round_trips_exactly(self):
        from untell.scripts.preserve import lock, restore

        masked, spans = lock(PAPER)
        assert restore(masked, spans) == PAPER


class TestTheLockAndTheProseExtractorShareOneList:
    """They had separate lists for about an hour, and in that hour `prose_only` scored the abstract
    and the theorem — text the loop is forbidden to edit. Optimising a number nothing can move is
    the same defect as scoring the masked string. Four other duplicated lists in this repository
    have drifted, so this one is imported rather than copied."""

    def test_preserve_uses_the_list_defined_in_latex(self):
        import untell.scripts.preserve as preserve
        from untell.scripts.latex import ENV_ALTERNATION

        assert preserve._LATEX_ENV_ALTERNATION is ENV_ALTERNATION

    @pytest.mark.parametrize("env", ["abstract", "theorem", "figure", "verbatim"])
    def test_a_locked_environment_is_dropped_from_the_prose(self, env):
        body = f"Ordinary prose here.\n\\begin{{{env}}}\nHIDDEN CONTENT\n\\end{{{env}}}\nMore prose."
        out = prose_only(body)
        assert "HIDDEN CONTENT" not in out, f"{env} content reached the score"
        assert "Ordinary prose" in out and "More prose" in out

    def test_a_container_environment_keeps_its_prose(self):
        """`document`, `itemize` and friends hold the text the user came here to humanize."""
        body = "\\begin{itemize}\n\\item The first point is important.\n\\end{itemize}"
        assert "first point" in prose_only(body)
        assert "itemize" not in LOCKED_ENVIRONMENTS


class TestProseExtraction:
    def test_it_detects_latex(self):
        assert is_latex(PAPER)
        assert not is_latex("A plain paragraph with a stray \\alpha in it and nothing else.")

    def test_markup_no_longer_dilutes_the_score(self):
        """MEASURED: the raw .tex scores 0.0949 where its prose scores 0.6261, so the loop read
        0.09, concluded the document passed, and returned it untouched."""
        from untell.scripts.score import score_text

        raw = score_text(PAPER, tier="lite")["max"]
        prose = score_text(prose_only(PAPER), tier="lite")["max"]
        assert prose > raw, f"prose {prose} not above raw source {raw}"

    def test_emphasis_keeps_its_words(self):
        """Dropping \\textbf{...} wholesale would delete words the reader plainly sees."""
        assert "important" in prose_only(r"This is \textbf{important} to note.")
        assert "nested" in prose_only(r"This is \textbf{\emph{nested}} emphasis.")

    def test_extraction_is_never_used_for_output(self):
        """It is a scoring view. The loop must still emit valid LaTeX."""
        from untell.scripts.run import untell_text

        result = untell_text(PAPER, tier="lite", rewriter="composite")
        assert "\\begin{document}" in result["final"]
        assert "\\cite{lee2019}" in result["final"]


class TestCitationSurvival:
    """Preserve-locking stops a key being EDITED. It cannot stop a whole sentence being dropped or
    merged, taking its `\\cite` with it — the document still compiles, and the claim that needed
    the source is simply no longer attributed."""

    def test_keys_are_extracted_including_multi_key_commands(self):
        assert cite_keys(PAPER) == ["smith2020", "lee2019"]
        assert cite_keys(r"See \cite{a,b, c}.") == ["a", "b", "c"]

    def test_bib_keys_are_parsed(self):
        assert bib_keys(BIB) == {"smith2020", "lee2019"}

    def test_an_undefined_key_is_reported(self):
        assert unresolved_citations(r"See \cite{ghost2099}.", BIB) == ["ghost2099"]
        assert unresolved_citations(PAPER, BIB) == []

    def test_a_lost_citation_is_reported(self):
        rewritten = PAPER.replace(r" \cite{lee2019}", "")
        assert dropped_citations(PAPER, rewritten) == ["lee2019"]

    def test_multiplicity_is_counted(self):
        """A paper citing one key twice and coming back with one has lost an attribution, even
        though the key still appears somewhere in the file."""
        src = r"First \cite{a}. Second \cite{a}."
        assert dropped_citations(src, r"First \cite{a}. Second.") == ["a"]

    def test_a_faithful_rewrite_reports_nothing(self):
        rewritten = PAPER.replace("Moreover, it is crucial", "It is crucial")
        assert dropped_citations(PAPER, rewritten) == []

    def test_the_loop_keeps_every_citation(self):
        from untell.scripts.run import untell_text

        result = untell_text(PAPER, tier="lite", rewriter="composite")
        assert dropped_citations(PAPER, result["final"]) == []


class TestALockedSpanEndsASentence:
    """A sentinel stands for a heading or an environment — spans that terminate what preceded them.

    FOUND on this paper: `\\section{Introduction}` masks to a sentinel, so the `Moreover,` after it
    did not look sentence-initial. `_plain_register` substituted it instead of leaving it for
    `_strip_transitions` to delete, and the output carried the fragment "What is more." Not
    LaTeX-specific: it applies wherever a locked span precedes a sentence.
    """

    def test_a_transition_after_a_heading_is_stripped_not_substituted(self):
        import random

        from untell.scripts.run import untell_text

        for seed in range(6):
            random.seed(seed)
            final = untell_text(PAPER, tier="lite", rewriter="composite")["final"]
            assert "What is more" not in final, f"seed {seed}: transition substituted: {final}"

    def test_both_sentinel_forms_count_as_a_boundary(self):
        """`_plain_register` re-stashes sentinels as \\x00N\\x00, so checking only for the ⟦HZ⟧ form
        matched nothing on the path that needed it — the first fix looked right and changed
        nothing."""
        from untell.rewriter.structural import _at_sentence_start

        assert _at_sentence_start("⟦HZ0003⟧\n", len("⟦HZ0003⟧\n"))
        assert _at_sentence_start("\x003\x00 ", len("\x003\x00 "))
        assert not _at_sentence_start("a sentence continues ", len("a sentence continues "))
