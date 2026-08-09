"""Every catalogued tell category must fire on something.

Six of the twenty-five never fired across 400 labelled documents. The catalogue header defends
keeping them, and the defence is sound: they are the *modern* tells, and both corpora predate the
models that emit them. But that argument only holds if the patterns work. A regex that matches no
real text and is exercised by no test is indistinguishable from a broken one, and the defence would
hide the breakage indefinitely — the category would keep earning its place in the catalogue by
being unfalsifiable.

So each category gets one deliberately egregious example and has to catch it.

A note on how these probes were written, because it decides what the test is worth. The first
attempt was twenty-five sentences composed from the category *names* — "What does this mean for
you?" for `rhetorical_opener`, "the only constant is change" for `aphorism`. Twelve of them failed.
Not one was a bug: `rhetorical_opener` matches "Honestly?" and "Look," and "Here's the thing", and
`aphorism` matches "X is the new Y". The patterns are far narrower than their names suggest.

That is worth knowing on its own — anyone reading `by_category` output should not assume
`participial_trailer` means every participial trailer — but it also means these probes are written
*from the patterns*. They prove a category is reachable. They do not prove it is well-designed, and
a test built this way cannot: it would pass just as happily against a pattern that had been
narrowed to a single literal string. The precision figures in the catalogue header are what speak
to quality; this file speaks only to liveness.
"""

from __future__ import annotations

import pytest

from untell.scripts.tells import _CATEGORIES, score_tells

# One probe per category, written against the pattern rather than the category name.
PROBES: dict[str, str] = {
    "ai_vocab": "We delve into the rich tapestry of this realm to leverage robust synergy.",
    "formulaic_transition": "Moreover, the result holds. Furthermore, it generalises to new data.",
    "steering_opener": "Interestingly, the effect persists. Notably, it does so at every scale.",
    "negated_contrast": "It is not just a tool, it is a philosophy that changes everything.",
    "participial_trailer": "The system beat every baseline, highlighting the value of the method.",
    "vague_attribution": "Studies show that the effect is real, and experts agree it matters.",
    "cliche": "At the end of the day, this is a game changer that pushes the envelope.",
    "sycophancy": "Great question! The answer depends on what you are optimising for here.",
    "meta_closer": "The method works well. I hope this helps you with your own experiments.",
    "chatbot_artifact": "As an AI language model, I cannot provide personal opinions on this.",
    "inflated_copula": "The framework serves as a foundation and boasts strong empirical results.",
    "hedge_stacking": "The approach could potentially work, and it may eventually generalise too.",
    "false_range": "Whether you're a student or a professional, everything from tools to habits helps.",
    "markdown_artifact": "## Key Takeaways\n\nThe method is fast and the results are reproducible.\n",
    "filler_phrase": "Due to the fact that the data is noisy, we smooth it before any fitting.",
    "aphorism": "Attention is the new bottleneck, and every team is discovering that this year.",
    "rhetorical_opener": "Here's the thing. The benchmark was never measuring what we assumed.",
    "cutoff_disclaimer": "As of my last training update, I do not have access to real-time data.",
    "challenges_section": "The field faces several challenges. Future directions are discussed below.",
    "notability_padding": "The project received independent coverage and has been featured in the press.",
    # Counted outside _CATEGORIES, by the structural passes rather than a single regex.
    "em_dash": "The result — which nobody expected — was clear, and the cause — cost — was obvious.",
    "semicolon_crutch": "It works; it scales; it is cheap; it is fast; nobody disagrees at all here.",
    "rule_of_three": "It is fast. It is cheap. It is good. Simple. Clear. Direct. Nothing is wasted.",
    # These two need 60 words before they will report anything (_MIN_WORDS_FOR_REPETITION), and
    # openers need four sentences before a share is meaningful. A probe under those bars reads as
    # a dead pattern when the pattern is fine, which is how the first draft of this file failed.
    "repeated_phrasing": (
        "The system is designed to help users who need it. In practice the system is "
        "designed to help users at scale across teams. Overall the system is designed to "
        "help users everywhere they happen to work. Deployment is quick and the setup "
        "requires almost nothing beyond a single configuration file kept in the repository "
        "alongside the rest of the deployment scripts that the team already maintains."
    ),
    "repeated_sentence_openers": (
        "This shows one thing clearly enough for anyone reading the report to follow along. "
        "This shows another thing too, in a way that the earlier draft never managed. "
        "This shows a third thing as well, which nobody had expected going in. "
        "This shows a fourth thing entirely, and the pattern by now should be obvious "
        "to anyone who has read this far into the paragraph without skipping ahead."
    ),
}

STRUCTURAL = (
    "em_dash",
    "semicolon_crutch",
    "rule_of_three",
    "repeated_phrasing",
    "repeated_sentence_openers",
)

ALL_CATEGORIES = [name for name, _ in _CATEGORIES] + list(STRUCTURAL)


def test_every_category_has_a_probe() -> None:
    """Guards the guard: a category added without a probe would silently go unchecked."""
    missing = [c for c in ALL_CATEGORIES if c not in PROBES]
    assert not missing, f"no probe written for: {missing}"


def test_no_probe_names_a_category_that_no_longer_exists() -> None:
    """A renamed or deleted category leaves a probe that can never fail."""
    stale = [c for c in PROBES if c not in ALL_CATEGORIES]
    assert not stale, f"probe for category that does not exist: {stale}"


@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_category_fires_on_its_probe(category: str) -> None:
    fired = score_tells(PROBES[category])["by_category"]
    assert category in fired, (
        f"{category} did not fire on its own probe; fired instead: {sorted(fired)}"
    )


@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_probe_is_not_a_false_positive_magnet(category: str) -> None:
    """A probe that trips half the catalogue proves nothing about the category it names."""
    fired = score_tells(PROBES[category])["by_category"]
    assert len(fired) <= 4, (
        f"{category}'s probe fires {len(fired)} categories ({sorted(fired)}) — too "
        f"unspecific to demonstrate anything"
    )


def test_clean_prose_fires_nothing() -> None:
    """The other half of liveness: a catalogue that fires on everything is equally useless."""
    clean = (
        "The kettle boiled while I read the last few pages. Rain had started again, "
        "and the window fogged at the corners. I put the book down and went to look "
        "for a dry coat."
    )
    fired = score_tells(clean)["by_category"]
    assert not fired, f"plain prose tripped: {sorted(fired)}"
