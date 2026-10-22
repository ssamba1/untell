"""Past 6,000 words the meaning gates must still compare text that corresponds.

`aligned_chunks` cuts (source, rewrite) into paired pieces for the gates and takes the worst
piece. Below `_EXACT_ALIGN_LIMIT` it aligns the whole document with difflib; above it, that is
quadratic, so it used to fall back to cutting the REWRITE at the SOURCE's word indices. A rewrite
that drops or adds words drifts a sentence out of step within a few chunks, token overlap between
pieces that no longer correspond collapses, and the min-over-pieces gate vetoes every candidate.

MEASURED with this file's own `_corpus` and `_light_edit` (~4% of words dropped, ~9% added),
token-overlap gate:

    words     before    after
    4,660     0.860     0.860     exact path, unchanged
    7,456     0.004     0.812     a faithful light edit had read as unrelated text
    13,980    0.005     0.821

and in the loop, one iteration best_of=3: 6,893 words adopted a rewrite, 7,905 words adopted
nothing. tests/test_the_loop_still_works_past_the_scoring_cap.py failed for exactly this reason,
blamed on the scoring cap, which happens to sit near the same length.
"""

from __future__ import annotations

import random
import time

import pytest

from untell.scripts import quality
from untell.text_split import CHUNK_WORDS, _anchored_cut_points

_SUBJECTS = [
    "climate adaptation", "protein folding", "urban transit", "credit scoring", "soil carbon",
    "vaccine logistics", "grid storage", "coral restoration", "supply chains", "wildfire modelling",
]
_OPENERS = ["Moreover,", "Furthermore,", "Additionally,", "Notably,", "In conclusion,"]
_VERBS = ["leverages", "underscores", "delves into", "highlights", "showcases"]
_NOUNS = [
    "a robust framework", "the pivotal integration", "a multifaceted tapestry",
    "the comprehensive landscape", "a transformative paradigm",
]


def _corpus(paragraphs: int) -> str:
    """Paragraphs that share their phrasing: the hard case, because phrases recur everywhere.

    The same builder as tests/test_the_loop_still_works_past_the_scoring_cap.py."""
    out = []
    for i in range(paragraphs):
        s = _SUBJECTS[i % len(_SUBJECTS)]
        out.append(
            f"{_OPENERS[i % 5]} the study of {s} in region {i} {_VERBS[i % 5]} "
            f"{_NOUNS[i % 5]} for every stakeholder. It is important to note that {s} "
            f"demonstrates remarkable capabilities in trial {i}. {_OPENERS[(i + 2) % 5]} "
            f"researchers leveraged these seamless tools to accelerate discovery across the "
            f"{s} domain and beyond."
        )
    return "\n\n".join(out)


def _light_edit(text: str, seed: int) -> str:
    """Drop ~4% of words and add ~9%: a faithful rewrite moves words AND changes the length.

    The length change is what the old fallback could not survive. Cutting the rewrite at the
    source's indices hands all of the surplus to the last piece, which then has no counterpart."""
    rng = random.Random(seed)
    out = []
    for word in text.split():
        x = rng.random()
        if x < 0.04:
            continue
        if x < 0.10:
            out.append("really")
        out.append(word)
        if x > 0.99:
            out.extend(["and", "so", "on"])
    return " ".join(out)


def _cuts(aw: list[str], bw: list[str]) -> list[int]:
    k = -(-max(len(aw), len(bw)) // CHUNK_WORDS)
    return [round(len(aw) * n / k) for n in range(1, k)]


def _lands_on_the_same_words(aw: list[str], bw: list[str], cut: int, point: int) -> bool:
    """Do the words just after the cut in the rewrite mostly match those after it in the source?"""
    # Twelve words, half of them shared: a faithful edit can drop a word right at the cut and
    # insert three more just after it, which a narrower window reads as a miss.
    after_a, after_b = aw[cut : cut + 12], bw[point : point + 12]
    return sum(min(after_a.count(w), after_b.count(w)) for w in set(after_a)) >= 6


@pytest.mark.parametrize("paragraphs", [100, 300])
def test_every_cut_lands_on_corresponding_text(paragraphs):
    """The property itself: each cut in the rewrite sits where that cut sits in the source.

    Not "agrees with the exact matcher". On text this repetitive the exact whole-document matcher
    is itself sometimes wrong, anchoring through a gap into the next paragraph, and the anchored
    mapping was the right one where they differed. A forward-looking window was tried first and
    was worse than both, off by up to 1,795 words after latching onto a later repeat."""
    src = _corpus(paragraphs)
    aw, bw = src.split(), _light_edit(src, paragraphs).split()
    cuts = _cuts(aw, bw)
    points = _anchored_cut_points(aw, bw, cuts)
    wrong = [c for c, p in zip(cuts, points) if not _lands_on_the_same_words(aw, bw, c, p)]
    assert not wrong, f"{len(wrong)} of {len(cuts)} cuts landed on unrelated text, first at {wrong[0]}"


@pytest.mark.parametrize("paragraphs", [160, 300])
def test_a_light_edit_past_the_limit_is_still_similar(paragraphs, monkeypatch):
    """The property the loop depends on: a faithful edit of a long document passes the gate."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")  # the token-overlap gate, as measured above
    src = _corpus(paragraphs)
    assert len(src.split()) > 6000, "fixture no longer crosses the exact-alignment limit"
    sim = quality.similarity(src, _light_edit(src, paragraphs))
    assert sim > 0.6, f"a ~6% word edit of {len(src.split())} words scored {sim:.3f}"


def test_the_mapping_stays_cheap_on_a_very_long_document():
    """Why the limit exists: the whole-document matcher is quadratic, and this must not be."""
    src = _corpus(860)  # ~40,000 words
    aw, bw = src.split(), _light_edit(src, 2).split()
    t0 = time.perf_counter()
    points = _anchored_cut_points(aw, bw, _cuts(aw, bw))
    assert time.perf_counter() - t0 < 2.0
    assert points == sorted(points) and points[-1] <= len(bw)
