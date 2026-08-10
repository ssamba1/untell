"""A locked span that ends up starting a sentence has to be capitalised.

`lock` captures a span with the casing it had where it was found. The rewriter is then free to move
it, and splitting a sentence at a clause boundary can put a mid-sentence span at the front of a new
one. MEASURED on real output: "the New York Times" was locked out of "...published by various
organizations, and the New York Times is just one...", the loop split there, and restore wrote it
back verbatim:

    "...one of the most influential best seller lists in the book industry. the New York Times
     Best seller list is not the only one."

The masked candidate is clean — the lowercase sentence start does not exist until restore runs — so
no check on the rewriter's output could have caught it. It was found by scanning 60 real rewrites
for shapes the tell catalogue cannot see, which is also how the "a testament to" -> "a mark to"
break turned up.

The guard is narrow on purpose. Capitalising a span whose case is load-bearing is worse than the
lowercase sentence it fixes: "Doi:10.1000/xyz" in a citation is a corrupted identifier, where
"the New York Times" at a sentence start is merely untidy.
"""

from __future__ import annotations

import pytest

from untell.scripts.preserve import lock, restore

_SENTINEL = "⟦HZ0000⟧"


def _restore(masked: str, span: str) -> str:
    return restore(masked, {_SENTINEL: span})


class TestCapitalisedWhenItShouldBe:
    def test_after_a_full_stop(self) -> None:
        out = _restore(f"Alpha beta gamma. {_SENTINEL} is influential.", "the New York Times")
        assert out == "Alpha beta gamma. The New York Times is influential."

    def test_at_the_very_start(self) -> None:
        out = _restore(f"{_SENTINEL} is influential.", "the New York Times")
        assert out.startswith("The New York Times")

    @pytest.mark.parametrize("terminator", [".", "!", "?"])
    def test_after_any_terminator(self, terminator: str) -> None:
        out = _restore(f"Alpha{terminator} {_SENTINEL} follows.", "the report")
        assert f"{terminator} The report" in out


class TestLeftAloneWhenCaseIsLoadBearing:
    @pytest.mark.parametrize(
        "span",
        [
            "doi:10.1000/xyz",  # colon — capitalising corrupts the identifier
            "iPhone sales",  # internal capital
            "mRNA vaccines",  # internal capital
            "pH levels",  # internal capital
            "e.g. the report",  # abbreviation with dots
            "3 sites",  # starts with a digit
            "Smith (2020)",  # already capitalised
        ],
    )
    def test_span_is_written_back_verbatim(self, span: str) -> None:
        out = _restore(f"Alpha beta. {_SENTINEL} follows.", span)
        assert f". {span} follows." in out, f"restore altered {span!r}"

    def test_mid_sentence_spans_keep_their_casing(self) -> None:
        """The common case: a lowercase span that is still mid-sentence must stay lowercase."""
        out = _restore(f"Alpha beta {_SENTINEL} gamma.", "the New York Times")
        assert out == "Alpha beta the New York Times gamma."


def test_an_untouched_round_trip_is_the_identity() -> None:
    """The property everything else rests on: restore(lock(t)) == t when nothing moved."""
    for text in [
        "There are many lists published by various outlets, and the New York Times is just one.",
        "Smith (2020) reported 42 kg across 1,250 samples, per doi:10.1000/xyz and page 7.",
        "The trial ran for 12 weeks. Jones (2021) confirmed it at 97 percent agreement.",
    ]:
        masked, mapping = lock(text)
        assert restore(masked, mapping) == text
