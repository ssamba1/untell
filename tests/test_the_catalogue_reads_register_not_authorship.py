"""Same author, three registers — which separates the counts, who wrote it or how it is written?

Round eighty-one found the tell catalogue firing on 48.1% of human academic abstracts and 8.6% of
machine ones, and two explanations fitted: the catalogue is broken, or it reads *register* and
academic prose is not the register it flags.

Holding authorship constant separates them. Everything in `eval/data/generated_registers.py` and
`eval/data/generated_abstracts.py` was written by the same model in the same session. MEASURED:

    arm                      n    tells/100w    at least one tell
    machine: abstracts      70          0.15                 8.6%
    machine: assistant      12          7.36               100.0%
    machine: promotional    12          8.52               100.0%
    human: abstracts       634          1.12                48.1%

**Fifty times the tell density between two registers by one author**, and every assistant and
promotional passage carries at least one. Register against register the catalogue separates
perfectly — AUROC **1.0000** for assistant against abstract and for promotional against abstract —
while it cannot tell promotional from assistant apart at all (0.5625), which are its two target
registers.

✅ **So the catalogue is not broken. It is an excellent register classifier**, built from
assistant-style and marketing LLM output and accurate on it. It simply is not an authorship
classifier, and round eighty-one measured what happens when it is used as one.

✗ **The lite score is neither.** On the same register comparison it scores **0.5095** — a coin flip —
against 0.3538 on authorship. The catalogue at least detects something reliably.
"""

from __future__ import annotations

import statistics

import pytest

from eval.data.generated_abstracts import ABSTRACTS
from eval.data.generated_registers import ASSISTANT, PROMOTIONAL
from eval.detection_power import ranking_auroc
from untell.scripts.tells import score_tells


def _density(texts, low: int = 0, high: int = 10 ** 9) -> list[float]:
    """Tells per 100 words, optionally restricted to a length band.

    Density already divides out length, but the arms must still be matched: the promotional
    passages are 36-53 words and the abstracts run to 221, and `eval/arms.py` exists because
    comparing arms of different lengths measures length. The banded figures below are the claim; the
    unbanded ones are context.
    """
    out = []
    for text in texts:
        flat = " ".join(text.split())
        if low <= len(flat.split()) < high:
            out.append(score_tells(flat)["tells_per_100w"])
    return out


ACADEMIC = _density(ABSTRACTS)
CHAT = _density(ASSISTANT)
MARKETING = _density(PROMOTIONAL)

# Matched bands: the assistant passages are 60-84 words, the promotional ones 36-53.
ACADEMIC_60 = _density(ABSTRACTS, 60, 100)
CHAT_60 = _density(ASSISTANT, 60, 100)
ACADEMIC_30 = _density(ABSTRACTS, 30, 60)
MARKETING_30 = _density(PROMOTIONAL, 30, 60)


def test_the_catalogue_separates_register_perfectly_at_matched_length():
    """The finding, with the arms matched so it is register being measured and not length.

    MEASURED: at 60-100 words the same author's academic prose runs 0.092 tells per 100 words and
    the assistant prose 7.357. At 30-60 words the academic arm is exactly 0.000 against 8.523.
    """
    assert ranking_auroc(CHAT_60, ACADEMIC_60) == 1.0
    assert ranking_auroc(MARKETING_30, ACADEMIC_30) == 1.0
    assert statistics.mean(CHAT_60) > 50 * max(statistics.mean(ACADEMIC_60), 0.01)
    assert statistics.mean(ACADEMIC_30) == 0.0


def test_it_cannot_separate_its_two_target_registers_from_each_other():
    """Which is the right behaviour and confirms what the 1.0 above means. Assistant and marketing
    copy are both what the catalogue was built from; a detector that separated them too would be
    reading something other than the thing it flags."""
    assert 0.3 < ranking_auroc(MARKETING, CHAT) < 0.7


def test_the_density_gap_between_registers_is_enormous():
    assert statistics.mean(ACADEMIC) < 0.5
    assert statistics.mean(CHAT) > 5.0
    assert statistics.mean(CHAT) > 20 * statistics.mean(ACADEMIC)


def test_every_assistant_and_promotional_passage_carries_a_tell():
    """100% against 8.6% for the same author's academic prose."""
    for texts in (ASSISTANT, PROMOTIONAL):
        assert all(score_tells(" ".join(t.split()))["tells"] > 0 for t in texts)


def test_only_a_small_minority_of_the_same_authors_abstracts_do():
    flagged = sum(1 for t in ABSTRACTS if score_tells(" ".join(t.split()))["tells"] > 0)
    assert flagged / len(ABSTRACTS) < 0.2, f"{flagged}/{len(ABSTRACTS)}"


def test_the_arms_are_the_same_author_which_is_the_whole_design():
    """If these came from different sources the comparison would measure the sources. They do not:
    both files say so, and both were written in one session by one model."""
    from eval.data import generated_abstracts, generated_registers

    for module in (generated_abstracts, generated_registers):
        assert "language model" in module.__doc__ or "same language model" in module.__doc__
    assert "same author" in generated_registers.__doc__.lower()


@pytest.mark.parametrize("arm,name", [(ASSISTANT, "assistant"), (PROMOTIONAL, "promotional")])
def test_the_register_arms_are_usable_as_data(arm, name):
    assert len(arm) >= 10, f"{name}: only {len(arm)}"
    assert len(set(arm)) == len(arm), f"{name}: duplicates inflate n without adding data"
    assert all(len(" ".join(t.split()).split()) >= 30 for t in arm), f"{name}: a passage is short"
    # Each arm has to sit inside ONE band, or the matched comparisons above sample it unevenly.
    lengths = [len(" ".join(t.split()).split()) for t in arm]
    assert max(lengths) - min(lengths) < 60, f"{name}: spread {min(lengths)}-{max(lengths)}"
