"""The one quotation style British and academic house styles use was the one still rewritable.

The straight-single-quote rule was added deliberately, with a measurement, because `'single quotes'`
were 0 of 2 preserved. Curly single quotes were excluded in the same commit for a stated reason:
U+2019 is the typographic apostrophe, so `‘...’` cannot be told from "don’t" by shape alone.

The reason has a hole in it. **U+2018 is not an apostrophe** — nothing writes `don‘t` — so the
opening delimiter is unambiguous and can anchor the match. Only the close is in doubt, which makes
this rule strictly safer than the straight one it was excluded next to, where both ends are
ambiguous.

MEASURED through the shipped loop, with the transform actually known to fire (semicolon-to-sentence,
the one that damaged citations in Result 215), 2 styles:

    ‘the scheme paid for itself; the region kept the surplus’
        ->  ‘the scheme paid for itself. The region kept the surplus’    2 of 2 DAMAGED
    the same words in straight-single, curly-double, straight-double     0 of 6 damaged

    After: 0 of 2.

**The first probe found nothing.** It put a comma inside the quotation instead of a semicolon and
reported 0 of 20 damaged across ten categories — a clean bill of health for a rule that was broken.
The trigger has to be the transform that is known to fire; a plausible one is not enough.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.preserve import lock, restore
from untell.scripts.run import untell_text

LQ, RQ, AP = "‘", "’", "’"
INNER = "the scheme paid for itself; the region kept the surplus"
PROSE = (
    "Moreover, it is important to note that the follow-up work found the same pattern in every "
    "cohort. Furthermore, this underscores the robustness of the result across the sites. "
    "In today's fast-paced world, the finding matters for anyone planning a replication."
)
QUOTED = [
    ("curly single", LQ + INNER + RQ),
    ("straight single", "'" + INNER + "'"),
    ("straight double", '"' + INNER + '"'),
    ("curly double", "“" + INNER + "”"),
]
# Every one contains U+2019 as an apostrophe and no U+2018. This is the control that carries weight:
# the HC3 corpus the straight rule cites has 0 texts containing U+2018 in 160 halves, so it cannot
# test this rule at all and returns 0 spurious matches the way a dead regex does.
APOSTROPHE_DENSE = [
    f"The team{AP}s results didn{AP}t match Jones{AP} figures, and the councils{AP} plans weren{AP}t ready.",
    f"It{AP}s the councils{AP} own money that pays for it, and they don{AP}t forget that fact.",
    f"Don{AP}t assume the 1980{AP}s were quiet; they weren{AP}t, and the records show it.",
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("quoted", [q for _, q in QUOTED], ids=[n for n, _ in QUOTED])
def test_a_quotation_locks_as_one_span(quoted: str) -> None:
    _, spans = lock(f"The report said {quoted} when the committee met last spring.")
    assert quoted in spans.values(), spans


@pytest.mark.parametrize("quoted", [q for _, q in QUOTED], ids=[n for n, _ in QUOTED])
@pytest.mark.parametrize("style", ["default", "academic"])
def test_the_quotation_survives_the_shipped_loop(quoted: str, style: str) -> None:
    """The semicolon inside is the point. It is what the rewriter reaches for, and a quotation is
    the one thing in this repository that must come back word for word."""
    doc = f"The report said {quoted} when the committee met last spring. " + PROSE
    final = untell_text(doc, tier="lite", max_iters=3, style=style)["final"]
    assert quoted in final, final[:200]


@pytest.mark.parametrize("text", APOSTROPHE_DENSE, ids=["team", "councils", "decades"])
def test_an_apostrophe_is_not_read_as_a_quotation(text: str) -> None:
    """Guards the guard, and it is the whole reason the exclusion existed. A rule that locked from
    one apostrophe to the next would swallow the prose between them — worse than the gap it closes,
    and invisible in the output because the text would simply stop improving."""
    _, spans = lock(text)
    assert not [v for v in spans.values() if v.startswith(LQ) or v.endswith(RQ)], spans


def test_an_apostrophe_inside_a_quotation_does_not_end_it() -> None:
    """The case that decides where the closing delimiter is. `‘the dog’s bowl was full enough’` has
    a U+2019 in the middle; ending there would lock `‘the dog’` and leave the rest rewritable —
    the partial lock this file's own module calls the worst possible outcome."""
    quoted = f"{LQ}the dog{AP}s bowl was full enough{RQ}"
    _, spans = lock(f"The keeper said {quoted} to the inspector last week.")
    assert quoted in spans.values(), spans


@pytest.mark.parametrize("quoted", [q for _, q in QUOTED], ids=[n for n, _ in QUOTED])
def test_the_lock_round_trips(quoted: str) -> None:
    doc = f"The report said {quoted} when the committee met last spring."
    masked, spans = lock(doc)
    assert restore(masked, spans) == doc


def test_the_prose_around_a_quotation_still_changes() -> None:
    """A rule that swallowed the sentence would pass everything above."""
    doc = f"The report said {LQ}{INNER}{RQ} when the committee met. " + PROSE
    final = untell_text(doc, tier="lite", max_iters=3)["final"]
    assert final != doc
    assert "Moreover, it is important to note" not in final
