"""Cross-cutting guard: a chunker must respect its own width limit.

Three separate functions in this codebase have shipped the same defect — a "pack items until full"
loop whose size test is skipped for the FIRST item of each chunk:

    if current and count + n > limit:      # `current and` exempts the first item
        flush()

An item wider than the whole limit therefore can never be split. It is appended anyway and the
chunk goes out oversized, which the caller then truncates silently:

  * ``detectors/base.windowed_max``       — a 1600-word bullet list became one 1600-word window,
    and the adapter read ~380 words of it.
  * ``attacks/back_translation._chunk``   — a 350+ word sentence went whole to MarianMT, which
    dropped everything past 512 tokens and returned the partial translation as complete.
  * ``rewriter/structural._split_long_sentences`` — a related shape: it appended a terminator
    unconditionally and produced "retailers..".

Fixing them one at a time did not stop the third. This tests the CLASS: every chunker is fed input
with no natural split points and must still respect its limit, and lose nothing.

New chunkers belong in CHUNKERS below.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

# Input with no sentence terminators, no punctuation, no line breaks — nothing any splitter can
# use. This is the shape that defeats a boundary-based chunker, and it is what a transcript, a
# bullet list or a run-on sentence looks like to one.
NO_BOUNDARIES = " ".join(f"word{i}" for i in range(900))


class _FakeTok:
    """MarianMT-ish: two BPE tokens per word."""

    def __call__(self, text, **kwargs):
        if isinstance(text, list):
            text = text[0]
        return {"input_ids": list(range(len(text.split()) * 2))}


def _windowed_max_chunks(text: str) -> tuple[list[str], int]:
    from untell.detectors.base import WINDOW_WORDS, windowed_max

    seen: list[str] = []
    windowed_max(text, lambda w: seen.append(w) or 0.5)
    return seen, WINDOW_WORDS


def _back_translation_chunks(text: str) -> tuple[list[str], int]:
    from untell.attacks import BackTranslator

    bt = BackTranslator()
    tok = _FakeTok()
    chunks = bt._chunk(text, tok)
    # Its limit is in TOKENS; convert to the same word unit the assertions use.
    return chunks, (bt._MAX_TOKENS - 16) // 2


CHUNKERS = {
    "windowed_max": _windowed_max_chunks,
    "back_translation._chunk": _back_translation_chunks,
}


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_chunker_respects_its_limit_without_natural_boundaries(name):
    chunks, limit = CHUNKERS[name](NO_BOUNDARIES)
    assert chunks, f"{name} produced nothing"
    for c in chunks:
        assert len(c.split()) <= limit, (
            f"{name} emitted a chunk of {len(c.split())} words against a {limit}-word limit; "
            "the caller will truncate it silently"
        )


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_chunker_loses_nothing_without_natural_boundaries(name):
    chunks, _ = CHUNKERS[name](NO_BOUNDARIES)
    assert " ".join(chunks).split() == NO_BOUNDARIES.split(), f"{name} dropped or reordered words"


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_chunker_leaves_short_input_alone(name):
    short = "This is a short sentence. It has two of them."
    chunks, _ = CHUNKERS[name](short)
    assert len(chunks) == 1, f"{name} split input that already fits"


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_a_single_oversized_item_is_split(name):
    """The specific shape: ONE item wider than the whole limit, nothing else in the input.

    This is what the `current and` exemption lets through — with an empty buffer the size test is
    skipped, the item is appended, and the chunk goes out oversized. Deliberately separate from the
    900-word case above, because a chunker could pass that by splitting only later items.
    """
    one_long_item = " ".join(f"word{i}" for i in range(1200))
    chunks, limit = CHUNKERS[name](one_long_item)
    assert len(chunks) > 1, f"{name} left 1200 words as a single chunk"
    assert max(len(c.split()) for c in chunks) <= limit


def test_the_pre_split_helpers_exist():
    """Both fixes work by splitting an item BEFORE packing it. Pin that the helper is still there,
    since deleting it would silently restore the original behaviour with every test above still
    passing on shorter inputs."""
    from untell.attacks.back_translation import BackTranslator
    from untell.detectors.base import _split_to_width

    assert callable(_split_to_width)
    assert callable(BackTranslator._fit)
    # ...and that they actually subdivide, rather than returning the input unchanged.
    assert len(_split_to_width(" ".join(["w"] * 100), 10)) == 10
