"""Text cannot contradict itself, and the model does not know that.

MEASURED: `contradiction_score(doc, doc)` on a real 301-word RAID abstract returned **0.6091**,
over the 0.50 bar, so `meaning_preserved(text, text)` was False. For that document no rewrite could
ever be adopted — every draw was discarded against an unchanged original, and the loop burned every
iteration to return the input. 1 of 30 RAID documents and 3 of 60 across both corpora sat at or
above 0.25 on the identity case alone.

It is not an alignment bug: the offending chunk was byte-identical on both sides. A chunk is a
mid-document slice, so it begins mid-sentence ("extensively evaluated on a large dataset of SAS
images, showcasing…"), and an NLI model handed a fragment as both premise and hypothesis returns
noise. Comparing a string with itself is the one case whose answer is known in advance, so it is
answered directly rather than asked.

The other half of the check matters as much: skipping unchanged chunks must not blunt the veto,
because a gate that passes everything is worse than one that occasionally over-rejects.
"""

from __future__ import annotations

import pytest

from untell.scripts.entailment import (
    DEFAULT_CONTRADICTION_BAR,
    available,
    contradiction_score,
    meaning_preserved,
)
from untell.scripts.quality import similarity

_LONG = (
    "This paper presents a novel approach to synthetic aperture sonar image segmentation, which "
    "is a fundamental step in various underwater applications. The method is extensively "
    "evaluated on a large dataset of sonar images, showcasing its superior performance compared "
    "to state-of-the-art methods. Our experiments demonstrate improved segmentation accuracy "
    "across every operating condition we tested, and the runtime remains within the budget "
    "required for deployment on autonomous platforms. We further show that the approach "
    "generalises to unseen seabed types without retraining, which prior work did not achieve."
)


def _skip_without_nli():
    if not available():
        pytest.skip("NLI model unavailable")


@pytest.mark.parametrize(
    "text",
    [
        _LONG,
        "The drug reduced mortality by 30 percent in the treated group.",
        "One short sentence.",
        "A. B. C. D. E. F. G. H.",
    ],
    ids=["long", "single", "short", "fragments"],
)
def test_a_text_does_not_contradict_itself(text: str) -> None:
    _skip_without_nli()
    assert contradiction_score(text, text) == 0.0


@pytest.mark.parametrize("text", [_LONG, "The trial ran for 12 weeks across 5 sites."])
def test_the_gate_accepts_a_text_against_itself(text: str) -> None:
    """The property that failed: no rewrite of that document could ever be adopted."""
    _skip_without_nli()
    assert meaning_preserved(text, text, similarity(text, text), 0.76)


@pytest.mark.parametrize(
    "source,candidate,label",
    [
        ("The drug reduced mortality by 30 percent.", "The drug increased mortality by 30 percent.", "negation"),
        ("Revenue rose above costs in Q3.", "Revenue fell below costs in Q3.", "direction flip"),
        ("The method outperforms every baseline.", "The method underperforms every baseline.", "inverted claim"),
    ],
    ids=lambda v: v if isinstance(v, str) and " " not in v else "",
)
def test_the_veto_still_fires_on_a_real_inversion(source: str, candidate: str, label: str) -> None:
    """Skipping unchanged chunks must not blunt the veto it sits inside."""
    _skip_without_nli()
    score = contradiction_score(source, candidate)
    assert score is not None and score >= DEFAULT_CONTRADICTION_BAR, f"{label} scored {score}"
    assert not meaning_preserved(source, candidate, similarity(source, candidate), 0.76)


def test_an_inversion_inside_an_otherwise_unchanged_document_is_still_caught() -> None:
    """The exact shape the optimisation could have broken: one edited chunk among identical ones."""
    _skip_without_nli()
    flipped = _LONG.replace("improved segmentation accuracy", "degraded segmentation accuracy")
    assert flipped != _LONG
    assert not meaning_preserved(_LONG, flipped, similarity(_LONG, flipped), 0.76)


class TestMeaningLossDeepInADocument:
    """The gate missed content deletion past its truncation point, and only for LOSS.

    `_pair_probs` tokenises (premise, hypothesis) as one 256-token sequence, so each side gets
    roughly 128 words. `contradiction_score` was chunked to survive that; `entailment_score` was
    deliberately left whole-text, and entailment is the half that catches meaning LOSS — dropping
    content contradicts nothing. MEASURED before chunking it, deleting most of a sentence:

        loss after  10 words   entailment 0.0017   caught
        loss after 140 words   entailment 0.9800   MISSED
        loss after 280 words   entailment 0.9800   MISSED

    with contradiction at 0.003, similarity 0.965, and the numeral, certainty and polarity guards
    all clean — so the whole gate passed it. The repo's own worked example describes exactly this
    failure for INVERSION and records it as fixed; the loss half was still open.
    """

    _FILLER = (
        "The report covers procurement, staffing, and the maintenance backlog across regional "
        "offices. "
    )
    _TAIL = (
        " The trial enrolled patients from rural clinics and ran under close supervision by an "
        "external board."
    )

    def _pair(self, pad_words: int) -> tuple[str, str]:
        pad = " ".join((self._FILLER * 40).split()[:pad_words])
        return pad + self._TAIL, pad + " The trial ran."

    @pytest.mark.parametrize("depth", [10, 140, 280, 400], ids=lambda d: f"{d}w")
    def test_content_deletion_is_caught_at_any_depth(self, depth: int) -> None:
        _skip_without_nli()
        source, cut = self._pair(depth)
        assert not meaning_preserved(source, cut, similarity(source, cut), 0.76), (
            f"content deleted after {depth} words passed the gate"
        )

    @pytest.mark.parametrize("depth", [140, 400], ids=lambda d: f"{d}w")
    def test_the_lexical_guards_are_not_what_catches_it(self, depth: int) -> None:
        """The probe has no numbers, hedges or polarity words, so only the NLI half can catch it.

        Without this, a fixture containing "five sites" would be caught by `numbers_kept` and the
        test would pass while the hole stayed open — which is what happened to the first version.
        """
        from untell.scripts.hedges import certainty_kept, polarity_kept
        from untell.scripts.numerals import numbers_kept

        source, cut = self._pair(depth)
        assert numbers_kept(source, cut)
        assert certainty_kept(source, cut)
        assert polarity_kept(source, cut)


def test_a_faithful_reorder_still_passes() -> None:
    """Chunking entailment was reverted once for false vetoes; this is the shape that caused them."""
    _skip_without_nli()
    a = "The committee approved the plan on Tuesday after a long review."
    b = "On Tuesday, after a long review, the committee approved the plan."
    assert meaning_preserved(a, b, similarity(a, b), 0.76)
