"""A chatbot sign-off is scaffolding and can be deleted. A sentence wearing one is not.

Sweeping every tell category over 120 corpus texts for "detected, and does the rewriter reduce it"
found three the catalogue counts and nothing could act on:

    false_range           2 flagged, 0 reduced
    meta_closer           1 flagged, 0 reduced
    challenges_section    1 flagged, 0 reduced

`meta_closer` is the one with an obvious safe action — "I hope this helps!" carries no content, so
removing it is a deletion of scaffolding rather than a rewrite. MEASURED on four sign-offs appended
to a real paragraph: the tell goes 1 -> 0, similarity 0.981-0.997, `passes` True, `contradicts`
False, numerals kept.

**The first version of the transform deleted a paragraph's conclusion.** The one real corpus instance
is

    "I hope this helps to explain why we might not have high resolution color cameras on some space
     probes and satellites."

— substance wearing a sign-off as a prefix. Removing the matched phrase leaves 17 words there
against 0 for "I hope this helps!", so the remainder is the test. Measured over seven sign-offs and
three content sentences beginning with the same phrases:

    scaffolding remainders   0, 0, 3, 4, 5, 5, 5
    content remainders       10, 11, 17

That corpus instance is therefore still counted and still not reduced, and correctly so — it is a
DETECTOR false positive, not a rewriter gap. A tell fix that deletes the user's last sentence is a
far worse defect than the tell.
"""

from __future__ import annotations

import logging

import pytest

from untell.rewriter.structural import _CLOSER_REMAINDER_WORDS, _strip_meta_closers
from untell.scripts.quality import passes, similarity

BODY = (
    "Salt lowers the freezing point of water, which is why it is spread on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed. "
    "Most councils mix it with grit so the surface also gains traction."
)

SCAFFOLDING = [
    "I hope this helps!",
    "I hope this helps.",
    "Let me know if you need anything else.",
    "Let me know if you have any other questions.",
    "Feel free to reach out if you need more detail.",
]

CARRIES_CONTENT = [
    "I hope this helps to explain why we might not have high resolution colour cameras.",
    "Let me know if the build fails on the new continuous integration runner tonight.",
    "I hope this helps you decide which of the three approaches fits your dataset best.",
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("closer", SCAFFOLDING, ids=lambda c: c[:22])
def test_a_pure_sign_off_is_removed(closer: str) -> None:
    text = f"{BODY} {closer}"
    out = _strip_meta_closers(text)
    assert out != text
    assert closer.rstrip(".!?") not in out


@pytest.mark.parametrize("ending", CARRIES_CONTENT, ids=lambda c: c[:22])
def test_a_sentence_wearing_a_sign_off_is_kept(ending: str) -> None:
    """Guards the guard, and it is the whole reason for the remainder rule. The first version of
    this transform deleted the corpus's one real instance, which is a paragraph's conclusion."""
    text = f"{BODY} {ending}"
    assert _strip_meta_closers(text) == text


def test_several_stacked_sign_offs_all_go() -> None:
    text = f"{BODY} I hope this helps! Let me know if you have questions."
    out = _strip_meta_closers(text)
    assert "hope this helps" not in out and "Let me know" not in out


def test_a_sign_off_mid_document_is_not_touched() -> None:
    """"Let me know if the build fails" early in a document is an instruction to a reader."""
    text = f"Let me know if the build fails. {BODY}"
    assert _strip_meta_closers(text) == text


def test_a_document_that_is_only_a_sign_off_is_not_emptied() -> None:
    assert _strip_meta_closers("I hope this helps!") == "I hope this helps!"


@pytest.mark.parametrize("closer", SCAFFOLDING, ids=lambda c: c[:22])
def test_the_deletion_survives_the_meaning_gate(closer: str) -> None:
    """Deleting a sentence is the one move in this file that removes content outright, so the gate
    that exists to catch that has to be asked."""
    text = f"{BODY} {closer}"
    out = _strip_meta_closers(text)
    assert passes(text, out), similarity(text, out)
    assert similarity(text, out) >= 0.95


def test_the_threshold_sits_between_the_two_measured_groups() -> None:
    """Scaffolding remainders measured at 0-5, content at 10-17. A threshold outside that gap
    silently reverts this file to one of the two failures it documents."""
    assert 5 < _CLOSER_REMAINDER_WORDS < 10


def test_the_stripped_output_survives_the_real_meaning_gate() -> None:
    """The gate this transform actually faces, which Result 116 never asked.

    That result verified the strip with `passes()` — the similarity-only helper — and shipped. The
    loop calls `meaning_preserved`, and MEASURED against it the transform was rejected every time,
    by three different gates for three different reasons:

        certainty   "hope" is a hedge word, so deleting a sign-off drops a hedge CLASS
        length      two stacked closers are 13 words, over the 10-word deletion allowance
        roles       "I hope ...", "Let me know ..." are predicates that vanished

    The transform ran, produced correct output, and every candidate was thrown away. All three now
    read scaffolding-stripped text, normalised once in `entailment.strip_scaffolding`.
    """
    from untell.scripts.entailment import meaning_preserved

    for closer in ("I hope this helps!", "I hope this helps! Let me know if you have questions."):
        text = f"{BODY} {closer}"
        out = _strip_meta_closers(text)
        assert out != text, "premise: the transform must have fired"
        assert meaning_preserved(text, out, similarity(text, out), 0.76), closer


def test_a_real_deletion_is_still_rejected() -> None:
    """Guards the guard. The exemption must not become a hole: text that is not a sign-off still
    counts in full, so dropping a real sentence is still a veto."""
    from untell.scripts.entailment import meaning_preserved

    truncated = " ".join(BODY.split(". ")[:1]) + "."
    assert meaning_preserved(BODY, truncated, similarity(BODY, truncated), 0.76) is False


CARRIES_A_REFERENCE = [
    "I hope this helps [3]!",
    "I hope this helps, see [3] for the derivation.",
    "Let me know if you need the data (Smith 2020).",
    "I hope this helps https://example.org/paper.",
    "Let me know if you want the preprint, doi:10.1234/abcd.5678.",
]


@pytest.mark.parametrize("closer", CARRIES_A_REFERENCE, ids=lambda c: c[:26])
def test_a_sign_off_carrying_a_reference_is_kept(closer: str) -> None:
    """A remainder rule counts WORDS, and a citation is worth more than its length.

    FOUND by testing the README's promise that citations are kept intact. Every one of these was
    deleted as pure scaffolding, taking the reference with it — a numeric marker, an author-year
    citation, a URL and a DOI, each short enough to pass the six-word remainder test.

    The fix defers to `preserve._collect_spans` rather than adding a citation pattern here: that
    layer already covers both citation forms, URLs, DOIs, emails, identifiers, dates and
    quantities, and a private copy of any of it is the two-vocabularies defect this module has been
    on both sides of.
    """
    text = f"{BODY} {closer}"
    assert _strip_meta_closers(text) == text


def test_the_ordinary_sign_offs_still_go() -> None:
    """Guards the guard. Deferring to a preservation layer is only safe if it does not swallow the
    transform: a rule that kept every closer would make this file's whole subject a no-op."""
    for closer in SCAFFOLDING:
        text = f"{BODY} {closer}"
        assert _strip_meta_closers(text) != text, closer
