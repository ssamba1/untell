"""The fronting budget must see the fronting the text already has.

`_front_subordinate_clauses` moves a trailing subordinate clause to the front, up to the share of
eligible sentences humans actually front. The budget is `rate * eligible - already`, and `already`
is counted by `_FRONTED_RE`.

That regex contained a literal 0x08 byte where `\b` was meant — a word boundary mangled into a
backspace by a shell heredoc, sitting inside an `r"..."` string where it looked completely normal.
No text contains a backspace, so `already` was always 0 and the transform kept adding fronting to
text that was already at or over the human rate. Measured on a six-sentence block already fronting
three: 0.67 extra frontings per run before, 0.00 after.

The whole 2526-test suite passed with that regex dead. These tests are the ones that would not have.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import (
    _FRONTABLE,
    _FRONTABLE_RE,
    _FRONTED_RE,
    _HUMAN_FRONTING_RATE,
    _front_subordinate_clauses,
)

# Three already fronted, three with a trailing subordinate clause (so: eligible).
BLOCK = [
    "Although the corpus was fairly small, the effect was clear across every seed.",
    "Because the random seeds differed, the reported numbers moved by several points.",
    "When the register of the text changed, the calibrated constant changed with it.",
    "The whole pipeline runs quickly because the encoder we picked is unusually small.",
    "The summary table came out wrong because the parser silently dropped an entire row.",
    "Reviewers asked for the extra ablation although the deadline had already passed.",
]

ALREADY_FRONTED = BLOCK[:3]


@pytest.mark.parametrize("sentence", ALREADY_FRONTED)
def test_the_counter_recognises_a_fronted_sentence(sentence: str) -> None:
    """The direct check. `_FRONTED_RE` matching nothing is indistinguishable from a text that
    happens to front nothing, which is why this went unnoticed for so long."""
    assert _FRONTED_RE.match(sentence), (
        f"_FRONTED_RE does not match an obviously fronted sentence: {sentence!r}. "
        "If it contains a control character again, the budget is silently always full."
    )


def test_the_pattern_holds_no_control_characters() -> None:
    """Names the actual failure rather than its symptom, so a future mangling reads as itself.

    `untell-audit` checks this repo-wide; this keeps the assertion next to the regex it broke.
    """
    for char in _FRONTED_RE.pattern:
        assert ord(char) >= 0x20 or char in "\t\n", (
            f"_FRONTED_RE contains U+{ord(char):04X} — a word boundary mangled into a control "
            "character. No text contains one, so the pattern can never match."
        )


def test_text_already_at_the_human_rate_gets_no_more_fronting() -> None:
    """The behaviour the counter exists for, over enough draws to see a fractional budget."""
    eligible = [s for s in BLOCK if _FRONTABLE_RE.match(s.strip())]
    assert eligible, "fixture no longer exercises the transform"
    already = sum(1 for s in BLOCK if _FRONTED_RE.match(s.strip()))
    assert already >= _HUMAN_FRONTING_RATE * len(eligible), "fixture is not over the human rate"

    changed = 0
    for seed in range(100):
        random.seed(seed)
        out = _front_subordinate_clauses(list(BLOCK), rate=1.0)
        changed += sum(1 for a, b in zip(BLOCK, out) if a != b)
    assert changed == 0, (
        f"{changed / 100:.2f} sentences fronted per run in text already over the human rate "
        f"({already} fronted of {len(eligible)} eligible, target "
        f"{_HUMAN_FRONTING_RATE * len(eligible):.1f})"
    )


def test_text_below_the_rate_still_gets_fronted() -> None:
    """Guards the guard: a transform that never fires would pass the test above too."""
    plain = [s for s in BLOCK if not _FRONTED_RE.match(s.strip())]
    assert plain, "fixture has no unfronted sentences"
    changed = 0
    for seed in range(100):
        random.seed(seed)
        out = _front_subordinate_clauses(list(plain), rate=1.0)
        changed += sum(1 for a, b in zip(plain, out) if a != b)
    assert changed > 0, "the transform now fires on nothing at all — the budget is stuck at zero"


def test_a_backspace_in_the_pattern_would_be_caught() -> None:
    """Proves the assertion above is not vacuous, by building the broken pattern deliberately."""
    mangled = re.compile(r"^(?:" + "|".join(_FRONTABLE) + r")" + chr(8) + r"[^,]{5,},", re.I)
    assert not any(mangled.match(s) for s in ALREADY_FRONTED), (
        "the mangled pattern matches something, so it was never the reason the counter read zero"
    )
