"""The opener budget must prefer duplicate openers.

structural.py:2516: `key=lambda i: (0 if counts.get(first_words[i], 0) > 1 else
1, random.random())` — sentences whose opening word repeats another's are
prioritized for the opener budget; single-occurrence openers only get it when
no duplicate exists. The mutation > -> >= makes count==1 words equally
eligible, so the budget randomly lands on non-duplicate openers instead of the
duplicates the transform exists to fix. Pinned with a seed sweep: 40 seeds, the
duplicate must win every time under the original (0.25^40 is not a thing that
happens), while the mutant wins 11/40.
"""
import random

from untell.rewriter.structural import _vary_openers

SENTENCES = [
    "The cat sat down quietly.",
    "The dog ran away fast.",
    "Zebra eats grass daily.",
    "the zebra is striped now.",
]


def _nonduplicate_picks():
    picks = 0
    for seed in range(1, 41):
        random.seed(seed)
        out = _vary_openers(SENTENCES, rate=0.25, seen={})
        for i, (before, after) in enumerate(zip(SENTENCES, out)):
            if before != after and i == 2:  # Zebra — the non-duplicate opener
                picks += 1
    return picks


def test_budget_prefers_duplicate_openers():
    assert _nonduplicate_picks() == 0
