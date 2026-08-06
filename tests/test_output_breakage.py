"""Cross-cutting guard: the rewriter must not emit visibly broken English.

Three bugs came out of scanning real rewrites for mechanical breakage signatures, in one sitting:

  * "Actually, Issue #4821 tracks the release ..." — an opener prepended to an ordinary capital
  * "Put simply, also, wine is often shipped ..."  — an opener stacked on an existing marker
  * "... in the British government and. Were being dictated to ..." — a split stranding "and"

None of them could be caught by scoring. A detector rates broken text as *more* human — the
burstiness of a fragment looks like voice — so the loop will happily adopt a mangled candidate and
report a good number for it. The only thing standing between that and the user is a check like
this one.

The signatures are deliberately mechanical, not stylistic: each is something no competent writer
produces, so a hit is a bug rather than a matter of taste. New transforms belong here — this file
tests the CLASS, not the three instances.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import StructuralRewriter
from untell.text_split import split_sentences

# Long enough to trigger the split, merge and opener transforms, which only fire above a
# word-count threshold or at a rate.
SAMPLES = [
    "They also resented the fact that they had no representation in the British government and "
    "were being dictated to by officials who had no understanding of their needs or concerns. "
    "Additionally, the taxes were imposed without any consultation whatsoever, which many "
    "colonists regarded as a fundamental breach of their rights as subjects.",
    "Also, wine is often shipped and stored at specific temperatures to preserve its quality, "
    "which can also affect the final price a customer pays. Moreover, the storage costs are "
    "passed on to the consumer in almost every case, and the margins remain thin throughout.",
    "Furthermore, the organization leverages robust methodologies to optimize operational "
    "efficiency across a wide range of diverse sectors and geographies. Issue 4821 tracks the "
    "release that shipped last November, and the documentation explains the full setup process.",
]

SIGNATURES = [
    ("stranded conjunction", re.compile(
        r"\b(and|or|but|nor|yet|while|because|since|although|though|whereas|unless|until)\s*[.!?]",
        re.I)),
    ("stacked openers", re.compile(
        r"^(Actually|In practice|Broadly|In short|Looking at this|As it turns out|Put simply|"
        r"Realistically),\s+(However|Moreover|Furthermore|Also|Hence|Therefore|Thus|Additionally|"
        r"And|But|Plus|Then|Besides)\b", re.I)),
    ("comma before terminator", re.compile(r",\s*[.!?]")),
    ("doubled punctuation", re.compile(r"[,;:]{2,}")),
    ("doubled word", re.compile(r"\b(\w+)\s+\1\b", re.I)),
    ("comma after a preposition", re.compile(r"\b(of|to|in|on|at|by|with)\s*,\s*(that|this|the|it)\b", re.I)),
    ("space before punctuation", re.compile(r"\S\s+[,.;:](?:\s|$)")),
]


@pytest.mark.parametrize("text", SAMPLES)
@pytest.mark.parametrize("seed", range(12))
def test_the_structural_rewriter_emits_no_breakage_signatures(text, seed):
    random.seed(seed)
    out = StructuralRewriter().rewrite(text, {"max": 0.9})

    for label, pattern in SIGNATURES:
        # Only what the rewriter INTRODUCED. The samples are clean, but this keeps the check honest
        # if one ever gains a construction that trips a signature on its own.
        if pattern.search(text):
            continue
        for sentence in split_sentences(out):
            match = pattern.search(sentence)
            assert not match, f"{label}: {match.group(0)!r} in {sentence!r}"


def test_the_signatures_can_actually_fire():
    """A guard that matches nothing passes forever. Each pattern must catch its own example."""
    broken = {
        "stranded conjunction": "They had no representation in the British government and.",
        "stacked openers": "Put simply, also, wine is shipped cold.",
        "comma before terminator": "The result was clear ,.",
        "doubled punctuation": "The result was clear;; it held.",
        "doubled word": "The the result was clear enough.",
        "comma after a preposition": "On top of, that the clause applies.",
        "space before punctuation": "The result was clear .",
    }
    for label, pattern in SIGNATURES:
        assert pattern.search(broken[label]), f"{label} does not match its own example"


CONNECTIVE_SAMPLES = [
    "Moreover, the budget is approved. However, the timeline slipped by two weeks. "
    "Additionally, the team is smaller than planned, which makes the remaining work harder.",
    "However, salt is often the most effective and affordable option for many communities. "
    "Moreover, it is widely available. Furthermore, it stores well in most climates.",
]


@pytest.mark.parametrize("text", CONNECTIVE_SAMPLES)
def test_the_surgical_rewriter_emits_no_breakage_signatures(text):
    """The word-level path produced two of the three bugs this file was written for.

    Its swaps are punctuation-sensitive in a way the score cannot see: "however -> though" and
    "moreover -> and" are both correct words in the wrong syntactic position, and a detector reads
    the result as no worse — often better, since it is now less formulaic.
    """
    from untell.attacks import surgical_substitute

    out = surgical_substitute(text, tier="lite", threshold=0.30)["text"]

    extra = [
        ("sentence-initial subordinator", re.compile(r"(?:^|[.!?]\s+)(Though|Although|Whereas)\s*,", re.I)),
        ("coordinator with a comma", re.compile(r"\b(and|but|or|nor)\s*,\s", re.I)),
    ]
    for label, pattern in SIGNATURES + extra:
        if pattern.search(text):
            continue
        match = pattern.search(out)
        assert not match, f"{label}: {match.group(0)!r} in {out!r}"
