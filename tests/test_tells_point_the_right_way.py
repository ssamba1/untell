"""`tells/100w` must rank AI text above human text.

The defect row read: the headline naturalness metric "pointed backwards on real text". Re-derived
2026-08-09 at n=100 pairs per corpus it points the right way and separates widely — HC3 0.551 human
vs 7.335 AI, RAID 1.215 vs 12.884 — so the row is fixed. This test is what would catch it turning
around again, without needing the corpora at test time.

Offline fixtures on purpose. The corpus measurement is the authority and lives in
docs/free-ceiling-measured.md (Result 45); this is a direction guard, and a guard that needs a
network download is a guard that gets skipped in CI.
"""

from __future__ import annotations

import statistics

import pytest

from untell.scripts.tells import score_tells

# Assistant-register prose: formulaic transitions, inflated vocabulary, repeated framing.
AI_LIKE = [
    "Moreover, the framework leverages a robust approach to deliver meaningful outcomes at scale. "
    "Furthermore, it is important to note that the underlying methodology significantly enhances "
    "overall efficiency. In conclusion, this represents a substantial advancement in the field.",
    "It is worth noting that there are several key factors to consider. First, the system provides "
    "a comprehensive solution. Second, the system provides enhanced flexibility. Third, the system "
    "provides improved reliability across a wide range of deployment scenarios and environments.",
    "In today's rapidly evolving digital landscape, organizations must navigate an increasingly "
    "complex array of challenges. By leveraging cutting-edge technologies, businesses can unlock "
    "unprecedented opportunities for growth, innovation, and sustainable competitive advantage.",
    "Additionally, the proposed method demonstrates strong performance. Additionally, it offers "
    "considerable advantages over existing approaches. Additionally, the results underscore the "
    "importance of careful evaluation when assessing the overall effectiveness of such systems.",
]

# Forum and review register: uneven sentence length, concrete detail, ordinary vocabulary.
HUMAN_LIKE = [
    "I tried this for about a month. The battery died twice in the first week, which was annoying "
    "enough that I nearly returned it. Then it just... stopped doing that? No idea why. Been fine "
    "since. I'd buy it again but I'd tell people about the first week.",
    "Short answer: no. Longer answer: it depends what you mean by supported. The library still "
    "compiles against the old headers, and nobody has touched that code path since 2019, so you're "
    "on your own if something breaks. I'd budget a weekend.",
    "We moved house in March and the boiler packed in almost immediately. The plumber said it was "
    "original to the building, which would make it about forty years old. Replacing it cost more "
    "than the car. Anyway, warm now.",
    "My grandmother made this every Christmas and never wrote anything down. I've tried to "
    "reconstruct it three times and got it wrong three different ways. This version is close. The "
    "trick, I think, is not letting the butter get too warm before you start.",
]


def _rate(text: str) -> float:
    result = score_tells(text)
    return result["tells_per_100w"]


AI_RATES = [_rate(t) for t in AI_LIKE]
HUMAN_RATES = [_rate(t) for t in HUMAN_LIKE]


def test_ai_register_scores_higher_than_human_register() -> None:
    ai, human = statistics.mean(AI_RATES), statistics.mean(HUMAN_RATES)
    assert ai > human, (
        f"tells/100w is inverted: AI-register mean {ai:.2f} <= human-register mean {human:.2f}. "
        "The metric ranking human text as more machine-like is the original defect, not a "
        "regression in some transform."
    )


def test_the_gap_is_not_marginal() -> None:
    """Direction alone would survive a metric that had gone nearly flat."""
    ai, human = statistics.mean(AI_RATES), statistics.mean(HUMAN_RATES)
    assert ai >= human + 1.0, f"AI {ai:.2f} vs human {human:.2f} — separation has collapsed"


def test_the_metric_actually_fires() -> None:
    """A catalogue that matched nothing would rank everything equal at zero and pass a direction
    check that used >=. It does not here, but the assertion is cheap and the failure is silent."""
    assert max(AI_RATES) > 0, "no AI-register fixture produced a single tell"


@pytest.mark.parametrize("text", HUMAN_LIKE, ids=lambda t: t[:24])
def test_no_human_fixture_outscores_every_ai_fixture(text: str) -> None:
    """Per-text rather than mean-only: one human paragraph beating the whole AI set would mean the
    ordering holds on average by luck."""
    assert _rate(text) < max(AI_RATES), (
        f"human-register text scores {_rate(text):.2f}, at or above the worst AI fixture "
        f"({max(AI_RATES):.2f})"
    )
