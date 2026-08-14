"""A citation with a semicolon or a `see` in it was not a citation as far as `lock()` was concerned.

FOUND by asking whether any transform can damage a preserved span, then measuring the END rather
than the means. `lock`/`restore` round-trips cleanly on every hostile input tried — 18 pipeline runs
over citation-, URL-, quote- and entity-dense documents leaked no sentinel and altered no locked
span, and a document with 84 spans round-tripped exactly. The round-trip was never the problem.
**Coverage** was: a span that is never locked cannot fail to restore.

The parenthetical rule demanded a capitalised author immediately after `(` and closed at the first
`)`. So a multi-work or prefixed citation matched nothing, the parenthesis stayed open to the
rewriter, and the semicolon-to-sentence transform edited inside it. MEASURED through the shipped
loop, 8 citation forms x 2 styles, `max_iters=3`:

    (Smith, 2019; Jones, 2020)   ->  (Smith, 2019. Jones, 2020)     DAMAGED
    (Smith 2019; Jones 2020)     ->  (Smith 2019. Jones 2020)       DAMAGED
    (see Smith, 2019)            ->  (see Smith. 2019)              DAMAGED
    (cf. Smith 2019; Jones 2020) ->  (cf. Smith 2019. Jones 2020)   DAMAGED
    (Smith, 2019) and 4 others   ->  unchanged                      intact

    8 of 16 runs damaged, before. 0 of 16 after; 0 of 10 negative controls newly frozen.

Single-work forms were never damaged, which is why this survived a suite with 405 passing assertions
about preservation: every citation in every existing example is one work. The forms that break are
the ones academic prose uses to cite a literature rather than a paper.

`(e.g., Smith, 2019)` was NOT damaged before the fix and is covered anyway — it fragmented into
three spans, so it was one transform away from the same outcome for no reason worth keeping.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.preserve import lock, restore
from untell.scripts.run import untell_text

# Enough tell-heavy prose after the citation that the rewriter certainly acts on the document.
PROSE = (
    "Moreover, it is important to note that the follow-up work found the same pattern in every "
    "cohort. Furthermore, this underscores the robustness of the result across the sites. "
    "In today's fast-paced world, the finding matters for anyone planning a replication."
)
DAMAGED = [
    "(Smith 2019; Jones 2020)",
    "(Smith, 2019; Jones, 2020)",
    "(see Smith, 2019)",
    "(cf. Smith 2019; Jones 2020)",
]
ALREADY_WORKED = [
    "(Smith, 2019)",
    "(Smith 2019)",
    "(Smith et al., 2019)",
    "(Smith, 2019, p. 44)",
    "(Smith & Jones, 2019)",
    "Smith (2019)",
    "Smith et al. (2019)",
    "[12]",
    "[12, 14, 19]",
]
NOT_CITATIONS = [
    "(He was born in 1984)",
    "(see the appendix)",
    "(compare the two runs below)",
    "(see Table 3 for the split)",
    "(the trial ran for 2019 days)",
    "(see Smith and the others in that year)",
    "(cf. the earlier discussion)",
    "(e.g., the two runs above)",
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("cite", DAMAGED + ALREADY_WORKED, ids=lambda c: c)
def test_a_citation_locks_as_exactly_one_span(cite: str) -> None:
    """One span, not several. Fragmenting a citation into an author lock and a year lock leaves the
    punctuation BETWEEN them rewritable, which is exactly the damage measured above."""
    _, spans = lock(f"The effect held {cite} across every site that the team tested.")
    assert list(spans.values()) == [cite], spans


@pytest.mark.parametrize("cite", DAMAGED, ids=lambda c: c)
@pytest.mark.parametrize("style", ["default", "academic"])
def test_the_citation_survives_the_shipped_loop(cite: str, style: str) -> None:
    """The property the fix is for, asserted where the user meets it rather than at the lock."""
    doc = f"The effect held {cite} across every site that the team tested. " + PROSE
    final = untell_text(doc, tier="lite", max_iters=3, style=style)["final"]
    assert cite in final, final[:200]


@pytest.mark.parametrize("text", NOT_CITATIONS, ids=lambda t: t)
def test_an_ordinary_parenthesis_is_not_frozen(text: str) -> None:
    """Guards the guard, on the axis that matters for a widened pattern. Over-locking is the more
    expensive error: a frozen span is prose the rewriter can never improve, silently and forever,
    and nothing in the output would ever show it. `(He was born in 1984)` is the shape at risk —
    a capital, then a year, inside parentheses."""
    _, spans = lock(text)
    assert not [v for v in spans.values() if "(" in v and len(v) > 12], spans


def test_the_prose_around_a_citation_still_changes(stdlib_lite) -> None:
    """The same guard end to end. A pattern that swallowed the sentence would pass every assertion
    above — the citation survives perfectly inside text nothing can touch.

    Scoring path pinned to stdlib lite, exactly as test_the_prose_around_a_quotation_
    still_changes in test_a_curly_quotation_is_locked_too.py: on a torch machine
    `tier="lite"` upgrades to GPT-2 perplexity, which scores this PROSE 0.036 — the loop
    correctly sees an already-passing document, returns it unchanged, and `final != doc`
    fails through no fault of the lock. The assertion is about the lock, not the model.
    """
    doc = "The effect held (Smith, 2019; Jones, 2020) across every site tested. " + PROSE
    final = untell_text(doc, tier="lite", max_iters=3)["final"]
    assert final != doc
    assert "Moreover, it is important to note" not in final


@pytest.mark.parametrize("cite", DAMAGED + ALREADY_WORKED, ids=lambda c: c)
def test_the_lock_round_trips(cite: str) -> None:
    """The property that was never broken, pinned because the widened pattern is new code and this
    is what it would break first. `restore` returning the original is the contract every other
    assertion here rests on."""
    doc = f"The effect held {cite} across every site that the team tested."
    masked, spans = lock(doc)
    assert restore(masked, spans) == doc


def test_a_sentinel_in_the_input_is_not_corrupted() -> None:
    """Recorded from the same sweep. Text that already contains a sentinel-shaped token round-trips
    unchanged — `lock` claims those literals first so `restore` cannot rewrite the user's own text.
    Cheap to keep, and the failure mode is silent corruption of the input."""
    for probe in (
        "The build printed ⟦HZ0⟧ to the log and stopped.",
        "See ⟦HZ0⟧ and (Smith et al., 2019) together.",
        "Literal brackets ⟦ and ⟧ alone.",
    ):
        masked, spans = lock(probe)
        assert restore(masked, spans) == probe
