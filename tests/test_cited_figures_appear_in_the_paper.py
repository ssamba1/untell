"""A figure credited to a paper should be in that paper.

`verify_citations` proves a cited Anthology id resolves to a real paper. It says nothing about
whether the *number* attached to that citation is one the paper reports — and that is a failure this
repository has actually shipped: Beemo was published here as "11 detectors across 33 configurations"
when its abstract says only 33 configurations, the 11 coming from the authors' repository. The id
resolved perfectly. Nothing caught it except reading the abstract by hand.

`unsupported_figures` is the mechanical version of that read. It is deliberately a review list
rather than a pass/fail check: a paragraph legitimately mixes the cited paper's numbers with our own
measurements and with figures credited to another author by name, so a hit means "confirm a reader
cannot misattribute this", not "this is wrong". These tests pin the mechanics, which is the part
that would silently break.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eval import litreview

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / ".anthology-cache"

needs_corpus = pytest.mark.skipif(
    not (CACHE.exists() and any(CACHE.glob("*.xml"))),
    reason="Anthology corpus not cached (run `python -m eval.litreview --download`)",
)


def test_figure_forms_cover_the_spellings_one_number_takes():
    """`186K` in an abstract and `186,000` in a document are the same figure. Missing that would
    report a correctly-cited number as unsupported."""
    assert "186000" in litreview._figure_forms("186K")
    assert "186,000" in litreview._figure_forms("186K")
    assert "9" in litreview._figure_forms("9%")
    # A trailing zero is not significant: 6.40 and 6.4 are one number.
    assert "6.4" in litreview._figure_forms("6.40")


def test_normalise_makes_the_multiplication_sign_searchable():
    """Documents write `8.2×`; abstracts write `8.2 times`."""
    assert "times" in litreview._normalise("8.2× more likely")
    assert "186000" in litreview._normalise("186,000 articles")


@needs_corpus
def test_the_abstract_index_returns_abstracts_not_titles():
    """The bug that made the first run of this check report the whole corpus as unsupported:
    `paper_index` returns titles, and comparing figures against titles matches almost nothing."""
    index = litreview.abstract_index(CACHE)
    pid = "2026.acl-long.663"
    if pid not in index:
        pytest.skip(f"{pid} not in the cached volumes")
    entry = index[pid]
    assert len(entry) > 400, "an abstract, not just a title"
    assert "186K" in entry


@needs_corpus
def test_a_paper_whose_figures_we_quote_verbatim_is_not_flagged():
    """The journalism audit is quoted number-for-number from its abstract. If the checker reports
    those, it is broken — and a checker that cries wolf gets ignored."""
    findings = litreview.unsupported_figures(REPO, CACHE)
    journalism = [f for f in findings
                  if f["paper"] == "2026.acl-long.663" and f["document"] == "ai-writing-research.md"]
    assert not journalism, f"verbatim figures reported as unsupported: {journalism}"


@needs_corpus
def test_the_check_can_actually_fire(tmp_path):
    """Guards the guard. A checker that never reports anything is indistinguishable from a clean
    corpus, and this one is expected to be quiet most of the time."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "fake.md").write_text(
        "The paper ([2026.acl-long.663](https://aclanthology.org/2026.acl-long.663/)) audited "
        "**4242 newspapers** in total.\n", encoding="utf-8")
    findings = litreview.unsupported_figures(tmp_path, CACHE)
    assert any(f["figure"] == "4242" for f in findings), "a fabricated figure went unreported"


@needs_corpus
def test_a_paragraph_citing_several_papers_is_left_alone(tmp_path):
    """Attribution is only unambiguous with one citation in the paragraph. Guessing which of three
    papers a number belongs to would generate noise, and noise is how this gets switched off."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "fake.md").write_text(
        "Two papers ([2026.acl-long.663](https://aclanthology.org/2026.acl-long.663/) and "
        "[2025.naacl-long.357](https://aclanthology.org/2025.naacl-long.357/)) report "
        "**4242 things**.\n", encoding="utf-8")
    assert not litreview.unsupported_figures(tmp_path, CACHE)


@needs_corpus
def test_years_and_list_ordinals_are_not_treated_as_figures(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "fake.md").write_text(
        "**1. The 2025 audit.** See "
        "[2026.acl-long.663](https://aclanthology.org/2026.acl-long.663/).\n", encoding="utf-8")
    assert not litreview.unsupported_figures(tmp_path, CACHE)
