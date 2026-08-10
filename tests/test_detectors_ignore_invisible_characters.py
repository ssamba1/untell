"""No detector may change its verdict because of characters that do not render.

MEASURED on a human-written paragraph, inserting a soft hyphen between every character — which is
exactly what extracting text from a justified PDF produces:

    clean          max 0.1295   flagged False
    soft-hyphened  max 1.0000   flagged True

mage went 0.0 -> 1.0 and roberta_openai 0.033 -> 1.0. A false positive at certainty 1.0000, on
somebody's own writing, reachable by pasting it out of a PDF. `score_tells` has scrubbed invisible
codepoints since Result 51 and was unaffected (59 words either way) — only the detector half of the
product was reading a different document than the tells half.

These tests are written over the REGISTRY rather than over the adapters that were known to be
broken. The same defect has now appeared three times in this area — a normaliser scoped to
`[ \\t]{2,}`, then one scoped to `[ \\t]+`, then invisible characters missed entirely — and each
time the fix was correct and the scope was not. A per-adapter test would have to be remembered for
adapter number eight; this one cannot be.
"""

from __future__ import annotations

import pytest

from untell.detectors import load_detectors
from untell.detectors.base import normalise_for_scoring

# Every invisible we have seen arrive in real input. Soft hyphens come from PDFs, zero-width spaces
# from web copy-paste and watermarking, the joiners from both.
INVISIBLES = {
    "soft hyphen (PDF extraction)": "­",
    "zero-width space": "​",
    "zero-width non-joiner": "‌",
    "word joiner": "⁠",
    "left-to-right mark": "‎",
}

_SAMPLE = (
    "The committee published its findings on Tuesday after a review that had run for most of the "
    "year. Three of the seven recommendations concern procurement, and the rest deal with how "
    "records are kept between departments. The chair said the delay was caused by a backlog of "
    "submissions rather than any disagreement among the members of the review panel, and a second "
    "report covering the same period is expected before the end of the quarter."
)


def _interleave(text: str, ch: str) -> str:
    return "".join(c + ch for c in text)


def _available():
    dets = [d for d in load_detectors() if d.available()]
    if not dets:
        pytest.skip("no detectors available (needs torch + transformers)")
    return dets


class TestNormaliser:
    @pytest.mark.parametrize("name,ch", INVISIBLES.items(), ids=list(INVISIBLES))
    def test_invisible_characters_are_stripped(self, name: str, ch: str) -> None:
        assert normalise_for_scoring(_interleave("hello there", ch)) == "hello there"

    def test_word_count_survives(self) -> None:
        """The count is what everything else is derived from: 209 words became 889 without this."""
        dirty = _interleave(_SAMPLE, "­")
        assert len(normalise_for_scoring(dirty).split()) == len(_SAMPLE.split())

    def test_emoji_sequences_are_not_broken(self) -> None:
        """The reason this delegates to scrub_hidden instead of stripping the codepoints itself.

        A zero-width joiner holding a family emoji together is load-bearing; an orphan one is a
        watermark. A local stripper would not know the difference.
        """
        assert "\U0001f468‍\U0001f469‍\U0001f467" in normalise_for_scoring(
            "family \U0001f468‍\U0001f469‍\U0001f467 here"
        )

    def test_clean_text_is_untouched(self) -> None:
        assert normalise_for_scoring(_SAMPLE) == _SAMPLE


@pytest.mark.parametrize("name,ch", INVISIBLES.items(), ids=list(INVISIBLES))
def test_every_detector_ignores_invisible_characters(name: str, ch: str) -> None:
    """The contract, over the registry: adapter number eight inherits this without being edited."""
    dirty = _interleave(_SAMPLE, ch)
    for det in _available():
        clean_score = det.score(_SAMPLE)
        dirty_score = det.score(dirty)
        if clean_score is None and dirty_score is None:
            continue
        assert clean_score is not None and dirty_score is not None, (
            f"{det.name} abstained on only one of the two inputs ({name})"
        )
        assert abs(clean_score - dirty_score) < 1e-6, (
            f"{det.name}: {name} moved the score {clean_score:.4f} -> {dirty_score:.4f}"
        )


def test_the_pdf_paste_false_positive_is_closed() -> None:
    """The exact failure, end to end through the shipped scoring path."""
    from untell.scripts.score import score_text

    human = (
        "I spent five days in Lisbon last October and still have mixed feelings about it. The hills "
        "are the whole story and somehow never make the brochures. My hotel was up in Alfama, which "
        "photographs beautifully and translates, in practice, to climbing a six-story staircase "
        "every time I wanted coffee. By the second day my calves had opinions. I started planning "
        "each walk around which way was downhill, which is a strange way to see a city but probably "
        "an honest one."
    )
    _available()  # skip when no detector can run
    clean = score_text(human, tier="full")
    pasted = score_text(_interleave(human, "­"), tier="full")
    assert abs(clean["max"] - pasted["max"]) < 1e-6, (
        f"soft hyphens moved the verdict {clean['max']:.4f} -> {pasted['max']:.4f}"
    )
    assert clean["flagged"] == pasted["flagged"]
