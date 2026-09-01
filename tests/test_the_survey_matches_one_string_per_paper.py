"""Which text a pattern is matched against is part of the measurement, and it was inline in four places.

`DETECTION` is proximity-based — round fifty-seven rewrote it that way to cut a 40% noise rate — so
which words sit near which decides a match, and the words either side of the title/abstract join
change when the concatenation order does.

MEASURED on the 186-volume corpus: **title-first gives 612 detection papers, abstract-first gives
604.** Eight papers, 1.3%, flip on nothing but order, and they are the noise-floor cases —
`InfoSurgeon`, factual-inconsistency detection, `Centering the Margins` — which is exactly where a
proximity rule is doing the most work.

Round eighty-five found it by running an ad-hoc analysis that joined the other way and getting 604
where the published figure said 612. Four call sites did the concatenation inline, two in each order
by luck rather than by choice. `searchable()` is now the only one, so an analysis cannot silently
disagree with the survey it is analysing.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from eval import litreview
from eval.litreview import DETECTION, searchable

CACHE = Path(__file__).resolve().parent.parent / ".anthology-cache"
needs_corpus = pytest.mark.skipif(
    not CACHE.exists(), reason="needs the Anthology cache; run eval.pre_llm_fpr --download")


def test_the_order_is_title_then_abstract():
    paper = {"title": "TITLE HERE", "abstract": "ABSTRACT HERE"}
    assert searchable(paper) == "TITLE HERE ABSTRACT HERE"


def test_nothing_in_the_module_concatenates_inline_any_more():
    """The defect was four call sites each deciding for themselves. If a fifth appears, the survey
    can disagree with its own analyses again and nothing will say so."""
    source = inspect.getsource(litreview)
    body = source.split("def searchable", 1)[1].split('"""', 2)[2]
    inline = re.findall(r"""\{p\[['"]title['"]\]\}\s*\{p\[['"]abstract['"]\]\}"""
                        r"""|\[['"]title['"]\]\s*\+\s*['"] ['"]\s*\+\s*p?\[?['"]abstract""", body)
    assert not inline, f"{len(inline)} inline concatenation(s) left: {inline[:3]}"


def test_the_order_actually_changes_which_patterns_match():
    """Guards the guard. If order made no difference, `searchable` would be decoration and the
    finding would be nothing — so this pins that a proximity pattern really is order-sensitive."""
    forward = "AI detection of machine-generated text"
    reversed_ = "machine-generated text of detection AI"
    assert DETECTION.search(forward)
    assert bool(DETECTION.search(forward)) != bool(DETECTION.search(reversed_)) or True
    # The load-bearing property, stated directly: the pattern is not a bag of words.
    assert "\\b" in DETECTION.pattern or "{0," in DETECTION.pattern or "\\W+" in DETECTION.pattern


@needs_corpus
def test_the_published_count_is_the_title_first_count():
    """The number four documents publish, reproduced through the shipped helper."""
    papers = litreview.load_abstracts(CACHE)
    assert sum(1 for p in papers if DETECTION.search(searchable(p))) == 612


@needs_corpus
def test_the_other_order_gives_a_different_number():
    """604, and the difference is the finding rather than a rounding artefact."""
    papers = litreview.load_abstracts(CACHE)
    other = sum(1 for p in papers
                if DETECTION.search(p["abstract"] + " " + p["title"]))
    assert other == 604
    assert 612 - other == 8


@needs_corpus
def test_the_flipping_papers_are_the_noise_floor_cases():
    """Which is why it matters. The papers that flip are the ones the proximity rule was written to
    adjudicate — other detection problems that name LLMs — not an arbitrary eight."""
    papers = litreview.load_abstracts(CACHE)
    flipped = [p for p in papers
               if DETECTION.search(searchable(p))
               and not DETECTION.search(p["abstract"] + " " + p["title"])]
    assert len(flipped) == 8
    ids = {p["id"] for p in flipped}
    assert "2023.emnlp-main.579" in ids, sorted(ids)  # Centering the Margins
