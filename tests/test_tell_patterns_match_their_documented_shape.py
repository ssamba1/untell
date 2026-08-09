"""Four tells that fired on a probe but not on their own documented example.

``test_every_tell_category_can_fire.py`` proves each category is *reachable*, and says plainly in
its docstring that it cannot prove more: its probes are written from the patterns, so they would
pass just as happily against a regex narrowed to one literal string. This file is the other half.
Its probes are written from the shape the catalogue *describes*, and four categories failed them:

* ``cliche`` — ``despite (?:the )?challenges,? \\w+ continues to thrive``. The ``\\w+`` is a single
  token, so "Despite challenges, **the sector** continues to thrive" did not match, and the
  two-word subject is the more common of the two shapes.
* ``aphorism`` — reached "X is the ___ of Y" only when Y ended in web/internet/world/age/era, so
  the catalogue's own example, "Symmetry is the language of trust", scored zero.
* ``cutoff_disclaimer`` — covered the first-person forms ("as of my last training update") but not
  the impersonal hedge that actually survives into pasted output.
* ``notability_padding`` — covered "has been featured in" but not the roster form, where the list
  of outlets is itself the claim.

Recall for these four is low and that is intended: precision is the whole justification. Measured
across 600 (human, AI) pairs from RAID, HC3 and MAGE — 1,200 documents — the broadened patterns
fire on 0 human documents. The negatives below are the constructed near-misses that pin the
boundary, since the corpora cannot supply them: all three are ASCII-normalised news, review and QA
text, in which none of these four patterns occurs at all.
"""

from __future__ import annotations

import pytest

from untell.scripts.tells import score_tells

# (category, text) — the shape the catalogue describes, not the shape the regex happened to have.
DOCUMENTED_SHAPE: list[tuple[str, str]] = [
    ("cliche", "Despite challenges, the sector continues to thrive."),
    ("cliche", "Despite the ongoing challenges, its economy continues to grow."),
    ("cliche", "Despite these obstacles, the small team continues to flourish."),
    ("aphorism", "Symmetry is the language of trust."),
    ("aphorism", "Trust is the currency of collaboration."),
    ("aphorism", "Latency is the enemy of engagement."),
    ("aphorism", "Consistency is the bedrock of good design."),
    (
        "cutoff_disclaimer",
        "While details are limited in available sources, the outcome remains unclear.",
    ),
    ("cutoff_disclaimer", "Little public information is available about the founder."),
    (
        "notability_padding",
        "The work was cited in the New York Times, the BBC, the FT, and The Hindu.",
    ),
    ("notability_padding", "She has been profiled in Wired, Forbes, and The Atlantic."),
]

# Text that shares the grammar but is an ordinary true statement. Each one matched an earlier draft.
NEAR_MISSES: list[tuple[str, str]] = [
    # Bounded so it cannot reach across a sentence boundary for its verb.
    ("cliche", "Despite challenges at work I went home. The garden continues to thrive."),
    ("cliche", "Despite the rain, the market continues to open every Saturday."),
    # The aphorism branch keys on the noun, not the grammar.
    ("aphorism", "Paris is the capital of France."),
    ("aphorism", "He is the head of engineering."),
    # "language" and "currency" have literal senses; their literal subjects are excluded by name.
    ("aphorism", "French is the language of diplomacy in some circles."),
    ("aphorism", "The euro is the currency of Ireland."),
    # "price" was dropped from the noun list precisely because of this sentence's shape: it was the
    # only human false positive across all 1,200 measured documents.
    ("aphorism", "The cost of gasoline at the pump is the price of oil, plus shipping."),
    # "details are limited" needs the assistant framing, not any use of the words.
    ("cutoff_disclaimer", "Details are limited because the log had already been rotated."),
    # One or two outlets is ordinary sourcing. Three is what makes it a roster.
    ("notability_padding", "The study was cited in Nature."),
    ("notability_padding", "The result was covered by Reuters and the BBC."),
]


@pytest.mark.parametrize(
    "category,text", DOCUMENTED_SHAPE, ids=[f"{c}-{i}" for i, (c, _) in enumerate(DOCUMENTED_SHAPE)]
)
def test_fires_on_documented_shape(category: str, text: str) -> None:
    fired = score_tells(text)["by_category"]
    assert category in fired, (
        f"{category} missed the shape the catalogue documents: {text!r}; fired: {sorted(fired)}"
    )


@pytest.mark.parametrize(
    "category,text", NEAR_MISSES, ids=[f"{c}-{i}" for i, (c, _) in enumerate(NEAR_MISSES)]
)
def test_does_not_fire_on_near_miss(category: str, text: str) -> None:
    """The broadening must not have bought recall with false positives."""
    fired = score_tells(text)["by_category"]
    assert category not in fired, (
        f"{category} false-positived on ordinary prose: {text!r}; fired: {sorted(fired)}"
    )
