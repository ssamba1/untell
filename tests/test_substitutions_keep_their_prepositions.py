"""A word-for-word swap must not strand the preposition that followed it.

`word_importance._SYN` shipped ``"testament": ["proof", "sign", "mark"]``. "Testament" governs "to";
all three substitutes govern "of". Real output read:

    "It is a testament to the work."   ->  "It's a sign to the work."
    "A testament to the effort."       ->  "A mark to the effort."

Both are ungrammatical, and both look like progress to everything that measures this pipeline: the
`ai_vocab` hit is gone, the tell count dropped, and no detector parses. That is the failure mode
this file exists for — the metrics cannot see grammar, so the check has to be explicit.

Found by reading rewriter output rather than by a failing test, which is the only way this class
shows up.
"""

from __future__ import annotations

import pytest

from untell.rewriter.structural import StructuralRewriter
from untell.scripts.tells import score_tells

_REWRITER = StructuralRewriter()


def _rewrite(text: str) -> str:
    return _REWRITER.rewrite(text, score_tells(text))


TESTAMENT_FORMS = [
    "It is a testament to the work.",
    "This stands as a testament to the work.",
    "A testament to the effort.",
    "The result was a testament to years of careful engineering.",
    "Their success is a testament to the team.",
]

# A noun that governs "of" followed by "to" is the fingerprint of this bug, whichever entry causes
# it. Checked as bigrams so a future substitution that strands a preposition is caught here rather
# than in somebody's output.
STRANDED = [
    "proof to",
    "sign to",
    "mark to",
    "hallmark to",
    "indication to",
    "mix to",
    "array to",
    "range to",
]


@pytest.mark.parametrize("text", TESTAMENT_FORMS)
def test_testament_forms_come_out_grammatical(text: str) -> None:
    out = _rewrite(text).lower()
    for bad in STRANDED:
        assert bad not in out, f"stranded preposition in {out!r} (from {text!r})"


@pytest.mark.parametrize("text", TESTAMENT_FORMS)
def test_the_tell_is_actually_removed(text: str) -> None:
    """The other half: grammatical output is no good if "testament" is still sitting in it."""
    # Either category is correct depending on the form: the bare word is `ai_vocab`, while
    # "stands as a testament to" is a catalogued cliché and the longest-match span rule files it
    # there instead. What matters is that the probe starts with the tell present.
    fired = score_tells(text)["by_category"]
    assert {"ai_vocab", "cliche"} & set(fired), (
        f"the probe must start with the tell present, or removing it proves nothing: {fired}"
    )
    assert "testament" not in _rewrite(text).lower()


def test_no_single_word_substitute_strands_a_preposition() -> None:
    """Guards the table itself, so the next entry with this shape fails at import rather than later.

    Any headword in `_SYN` that is normally followed by "to" and whose substitutes take "of" would
    reproduce the bug. `testament` was the one that shipped; it now lives in structural.py's phrase
    table, which can rewrite the noun and the preposition together.
    """
    from untell.attacks.word_importance import _SYN

    of_governed = {
        "proof", "sign", "mark", "hallmark", "indication", "mix", "array", "range", "cornerstone",
    }
    to_governed = {"testament", "tribute", "gateway", "barrier", "alternative", "response"}
    offenders = [
        (head, sub)
        for head, subs in _SYN.items()
        if head in to_governed
        for sub in subs
        if sub in of_governed
    ]
    assert not offenders, (
        f"these swap a 'to' noun for an 'of' noun and strand the preposition: {offenders}"
    )


def test_no_substitute_is_a_clause_where_the_headword_was_a_noun() -> None:
    """A substitute has to be able to stand where the headword stood.

    `"effectiveness": [..., "how well it works"]` shipped, and this table substitutes word for word,
    so the clause landed in a noun slot: MEASURED in real rewriter output, "the effectiveness of our
    benchmark" became "the how well it works of our benchmark". `"accordingly": [..., "to match"]`
    is the same shape — a purpose phrase where a sentence adverb was, giving "the team to match
    revised the schedule" anywhere the original was not sentence-final.

    Both are the generalisation of the `testament` preposition case: the table matches a string and
    knows nothing about the slot it is filling.
    """
    from untell.attacks.word_importance import _SYN

    # A multi-word substitute opening with any of these is usually a clause or subordinate phrase
    # rather than the noun/adjective/adverb the headword is. "Usually" is doing real work: this is
    # a first-word proxy for a syntactic category, so it needs an exception list rather than
    # pretending to be exact.
    CLAUSE_HEADS = {"how", "what", "why", "when", "where", "it", "they", "is", "are", "to"}
    # "moreover" is a sentence adverb and "what is more" is an adverbial phrase — the same slot, and
    # idiomatic in every position "moreover" appears. Flagged by the proxy, correct in fact.
    ALLOWED = {("moreover", "what is more")}
    offenders = [
        (head, sub)
        for head, subs in _SYN.items()
        for sub in subs
        if len(sub.split()) > 1
        and sub.split()[0].lower() in CLAUSE_HEADS
        and (head, sub) not in ALLOWED
    ]
    assert not offenders, (
        f"clause-shaped substitutes that cannot fill their headword's slot: {offenders}"
    )


@pytest.mark.parametrize(
    "text,broken",
    [
        ("We demonstrate the effectiveness of our benchmark across datasets.", "the how well it works"),
        ("The effectiveness of the treatment was measured over twelve weeks.", "how well it works of"),
        ("The team revised the schedule accordingly after the review.", " the to match "),
    ],
)
def test_the_slot_break_does_not_appear_in_output(text: str, broken: str) -> None:
    import random

    for seed in range(12):
        random.seed(seed)
        assert broken not in _rewrite(text).lower(), f"seed {seed}: {_rewrite(text)!r}"
