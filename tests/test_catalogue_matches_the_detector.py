"""`ai-tells.md` and `tells.py` are a documentation/implementation pair, and nothing compared them.

The catalogue's headline section lists "the 20 highest-signal tells". Running a textbook example of
each against `score_tells` — no padding, and requiring the tell's OWN category rather than any
category — gives 13 of 16 that name a detector. The three that did not are all documentation
mismatches rather than dead code, and each needed a different answer:

  * **false_range** missed the catalogue's own quoted example. Item 17 gives "from ancient
    civilizations to modern startups"; the pattern required `to the`, and that half has no article.
    MEASURED over 120 HC3 and RAID pairs, dropping the article changes the counts by ZERO in both
    corpora — the shape does not occur there — so it was a free fix.

  * **rule_of_three** detects only the staccato form ("Fast. Simple. Effective."), deliberately.
    Its docstring records why the comma tricolon is excluded, with numbers: the POS-guarded slice
    has no signal and inverts on MAGE. The catalogue lists BOTH forms, so the doc over-promises.

  * **markdown_artifact** implements boilerplate section titles ("Key takeaways", "TL;DR"), not the
    heading/bullet density item 12 describes. Two different tells sharing a name.

The first is fixed here. The other two are recorded as known divergences rather than papered over —
narrowing the doc to match would lose real writing advice, and widening the detectors was measured
and rejected in their own docstrings.
"""

from __future__ import annotations

import logging
import pathlib

import pytest

from untell.scripts.tells import score_tells

CATALOGUE = pathlib.Path("untell/references/ai-tells.md")


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _categories(text: str) -> set[str]:
    result = score_tells(text, include_matches=True)
    return {k for k, v in (result.get("by_category") or {}).items() if v}


# (catalogue item, a textbook example of it, the category that must fire)
DETECTED = [
    ("em-dash", "The result — which nobody expected — changed everything about the plan.", "em_dash"),
    ("delve vocabulary", "We delve into the rich tapestry of the evolving landscape today.", "ai_vocab"),
    ("negated contrast", "It is not just a tool, it is a paradigm shift for everyone here.", "negated_contrast"),
    ("participial trailer", "The team shipped the release, marking a pivotal moment for them.", "participial_trailer"),
    ("vague attribution", "Studies show that research suggests experts believe this works.", "vague_attribution"),
    ("formulaic transition", "Moreover, the plan works well. Furthermore, it scales to any size.", "formulaic_transition"),
    ("sycophantic opener", "Certainly! Great question! Absolutely, I can help you with that.", "sycophancy"),
    ("closing meta", "I hope this helps! Let me know if you need anything else today.", "meta_closer"),
    ("inflated copula", "The building serves as a hub, represents a shift, and boasts more.", "inflated_copula"),
    ("adverb opener", "Interestingly, it works well. Notably, it scales. Importantly, cheap.", "steering_opener"),
    # The one this file fixed.
    ("false range", "From ancient civilizations to modern startups, this pattern applies.", "false_range"),
]


@pytest.mark.parametrize(("item", "example", "category"), DETECTED, ids=lambda x: str(x)[:20])
def test_the_catalogues_example_fires_its_own_category(item: str, example: str, category: str) -> None:
    """Its OWN category, not merely some category. Half a dozen of these also trip `cliche` or
    `ai_vocab`, and an "any category fired" check would pass for a detector that is dead."""
    assert category in _categories(example), f"{item}: {sorted(_categories(example))}"


def test_the_false_range_fix_does_not_catch_an_ordinary_range() -> None:
    """The article was the only thing standing between this pattern and every date range in the
    corpus — so removing it has to leave those alone. The scope word at the front is what actually
    does that work."""
    for ordinary in (
        "The meeting runs from Monday to Friday every week without exception.",
        "We drove from London to Paris in a single day last summer with friends.",
        "Costs rose from 10 to 20 percent over the same two-year period.",
    ):
        assert "false_range" not in _categories(ordinary), ordinary


KNOWN_DIVERGENCES = {
    "rule_of_three": (
        "The approach is fast, simple, and effective across every domain tested.",
        "detects the staccato form only; the comma tricolon is excluded with measurements",
    ),
    "markdown_artifact": (
        "# A\n\n## B\n\n### C\n\n- one\n- two\n- three\n- four\n- five\n- six\n- seven\n- eight",
        "detects boilerplate section titles, not heading/bullet density",
    ),
}


@pytest.mark.parametrize("category", sorted(KNOWN_DIVERGENCES), ids=lambda c: c)
def test_a_known_divergence_stays_documented(category: str) -> None:
    """These two do NOT fire on the catalogue's example, on purpose. Pinned so the divergence stays
    a decision on record: if one of them starts firing, the note above is stale and should be
    removed rather than left describing a limit that no longer exists."""
    example, _why = KNOWN_DIVERGENCES[category]
    assert category not in _categories(example), (
        f"{category} now fires on the catalogue's example — update the divergence note in this "
        "file's docstring, which says it does not"
    )


def test_the_catalogue_still_has_its_headline_section() -> None:
    """The examples above are quoted from it. If the section is renamed or dropped, they stop being
    quotations and become inventions."""
    text = CATALOGUE.read_text(encoding="utf-8")
    assert "highest-signal tells" in text
    assert "from ancient civilizations to modern startups" in text.lower()
