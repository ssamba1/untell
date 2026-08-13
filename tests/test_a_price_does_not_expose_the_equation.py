"""A currency `$` and a math `$` in one sentence paired with each other.

The inline-math rule was `\\$[^$\\n]{1,200}\\$`, which pairs the LEFTMOST two dollar signs it
finds. In prose that prices something and then states a formula, the first `$` is a currency sign,
so the pair it forms straddles the boundary between them. MEASURED on the shipped `lock()`:

    "The budget was $500 while $E=mc^2$ is the formula."
      -> 'The budget was ⟦HZ0000⟧E=mc^2$ is the formula.'

`$500 while $` went into the lock; `E=mc^2$` stayed in the text, visible to the rewriter. That is
the equation this rule exists to protect, exposed by nothing worse than a price earlier in the same
sentence. Substituting `F=ma` into the masked text and calling `restore` returns
"The budget was $500 while $F=ma$ is the formula." — a changed equation in an intact sentence.

`restore(lock(t)) == t` held in every case here, before and after. Round-trip fidelity is a
property of the sentinel bookkeeping, not of what the pattern chose to cover, so no round-trip test
could have seen this. These tests assert COVERAGE: the equation is inside a sentinel, and the prose
between two prices is not.

The mirror failure over-locks. "It cost $500 and then $700 in total." masked to
'It cost ⟦HZ0000⟧ in total.' — "and then" frozen as if it were part of an equation, four words the
rewriter may no longer touch.

The guard requires an inline span to look like math: a math indicator (\\ ^ _ = { } < > + |) before
the closing `$`, or a short unspaced token, and not a currency amount followed by a word. Genuine
math is unaffected — `$5 + 3 = 8$` opens with a digit but continues with an operator, not a word.
"""

from __future__ import annotations

import pytest

from untell.scripts.preserve import lock, restore

BACKSLASH = chr(92)  # `\alpha` written literally: an escape in a test source is a transport risk


def _locked_text(text: str) -> str:
    _masked, mapping = lock(text)
    return " ".join(mapping.values())


# (label, text, fragment that must end up INSIDE a sentinel)
COVERED = [
    ("currency then math", "The budget was $500 while $E=mc^2$ is the formula.", "E=mc^2"),
    ("the price too", "The budget was $500 while $E=mc^2$ is the formula.", "$500"),
    ("math then currency", "Given $E=mc^2$, the cost was $500 overall.", "E=mc^2"),
    ("bare symbol", "Let $x$ denote the rate.", "$x$"),
    ("digits as math", "The constant $500$ appears twice.", "$500$"),
    ("arithmetic", "We know $5 + 3 = 8$ holds.", "5 + 3 = 8"),
    ("subscript", "The term $a_i$ appears.", "a_i"),
    ("command", "The angle $" + BACKSLASH + "alpha$ is small.", BACKSLASH + "alpha"),
    ("braces", "We use $" + BACKSLASH + "frac{a}{b}$ here.", BACKSLASH + "frac"),
    ("text inside math", "Let $5 " + BACKSLASH + "text{ apples}$ be given.", BACKSLASH + "text"),
    ("display math", "See $$a^2+b^2=c^2$$ above.", "a^2+b^2=c^2"),
    ("bracket math", "See " + BACKSLASH + "[x=y" + BACKSLASH + "] above.", "x=y"),
]

# (label, text, prose that must stay OUTSIDE every sentinel — rewritable)
NOT_FROZEN = [
    ("two prices", "It cost $500 and then $700 in total.", "and then"),
    ("price per item", "The fee is $20 per item = $40 total.", "per item"),
    ("three prices", "We paid $10, then $20, then $30.", "then"),
]


@pytest.mark.parametrize("name,text,fragment", COVERED, ids=[c[0] for c in COVERED])
def test_math_is_inside_the_lock(name: str, text: str, fragment: str) -> None:
    masked, mapping = lock(text)
    assert fragment in _locked_text(text), (
        f"{name}: {fragment!r} was left in the text for the rewriter — masked to {masked!r}"
    )
    assert restore(masked, mapping) == text


@pytest.mark.parametrize("name,text,prose", NOT_FROZEN, ids=[c[0] for c in NOT_FROZEN])
def test_prose_between_two_prices_stays_rewritable(name: str, text: str, prose: str) -> None:
    """Over-locking is the other half of the same defect: a span that swallows ordinary words
    between two currency amounts removes them from the rewriter's reach for no reason."""
    masked, _mapping = lock(text)
    assert prose in masked, (
        f"{name}: {prose!r} was locked as if it were an equation — masked to {masked!r}"
    )


def test_a_rewrite_of_the_masked_text_cannot_change_the_equation() -> None:
    """The user-visible claim, end to end: substitute into the masked text the way a rewriter
    would, restore, and the formula must come back unchanged."""
    text = "The budget was $500 while $E=mc^2$ is the formula."
    masked, mapping = lock(text)

    rewritten = masked.replace("E=mc^2", "F=ma").replace("500", "600")
    assert restore(rewritten, mapping) == text, "the rewriter reached a locked fact"
