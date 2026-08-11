r"""biblatex citations were invisible to every report about them.

`CITE` matched `\(?:cite[a-zA-Z]*|nocite)` — commands that START with "cite", which is natbib and
APA. biblatex, the modern standard, puts the stem in the middle: \parencite, \textcite, \footcite,
\autocite. Those returned no keys at all, so:

  * `--against` printed "keeps every citation" on a rewrite that had destroyed all of them, and
  * no key was ever checked against the .bib.

`preserve.lock()` was never fooled. It masks LaTeX commands structurally, and MEASURED, all three
forms survive a full rewrite byte-exact — so the byte-locking promise held while the REPORTING on
it was blind. That combination is the dangerous one: the guarantee works and the check that would
tell you it stopped working does not.

The starred forms failed for a second reason: the star sits between the command and its optional
argument.
"""

from __future__ import annotations

import pytest

from untell.scripts.latex import cite_keys, dropped_citations

NATBIB = [(r"\citet{a}", ["a"]), (r"\citep{b,c}", ["b", "c"]), (r"\cite{d}", ["d"]),
          (r"\citeA{e}", ["e"]), (r"\nocite{f}", ["f"])]
BIBLATEX = [(r"\parencite{g}", ["g"]), (r"\textcite{h}", ["h"]),
            (r"\footcite{i}", ["i"]), (r"\autocite{j}", ["j"])]
STARRED = [(r"\citep*{k}", ["k"]), (r"\parencite*{l}", ["l"])]


@pytest.mark.parametrize("tex,expected", NATBIB + BIBLATEX + STARRED,
                         ids=[t for t, _ in NATBIB + BIBLATEX + STARRED])
def test_every_citation_command_family_is_recognised(tex: str, expected: list[str]) -> None:
    assert cite_keys(tex) == expected


@pytest.mark.parametrize("tex", [r"\section{Results}", r"\ref{tab:1}", r"\label{eq:loss}",
                                 r"\textbf{emphasis}"])
def test_a_non_citation_command_yields_nothing(tex: str) -> None:
    """Widening what counts as a citation must not turn every braced command into one."""
    assert cite_keys(tex) == []


def test_an_optional_argument_does_not_hide_the_key() -> None:
    assert cite_keys(r"\citep[see][p.~4]{jones2013}") == ["jones2013"]


def test_a_lost_biblatex_citation_is_reported() -> None:
    """The end the user sees. This printed "keeps every citation" before."""
    before = r"We follow \parencite{smith2023} and \textcite{jones2022} and \citep*{li2024}."
    after = r"We follow \parencite{smith2023} and \textcite{jones2022}."
    assert dropped_citations(before, after) == ["li2024"]


def test_nothing_is_reported_when_nothing_is_lost() -> None:
    """Guards the guard: a checker that always reports a loss is as useless as one that never does."""
    tex = r"We follow \parencite{smith2023} and \autocite{jones2022}."
    assert dropped_citations(tex, tex) == []
