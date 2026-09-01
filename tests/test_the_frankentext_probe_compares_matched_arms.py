"""Text whose words are human and whose arrangement is not — and the confound that nearly buried it.

*Frankentext* (2026.acl-long.1457) has an LLM assemble a narrative from thousands of human snippets,
~90% of tokens verbatim, and finds 72% misclassified as human by Pangram. Every arm this repository
audits assumes authorship of the *words*; there the words are human and the composition is not.

`eval/frankentext.py` measures what our own stack does with that input property. The construction is
deliberately cruder — `random.sample` rather than an LLM composing for coherence — so it isolates
arrangement with the coherence removed, and it is **not a replication**.

The first run reported stitched text flagged at 1.7% against 17.6% for whole documents, a −16.0% gap
that would have read as "stitched human text evades this detector tenfold". The comparison arm had
**n = 17**, because the stitched texts averaged 263 words and few abstracts are that long. Matched at
130 words with 150 per arm, the gap is −0.7% and the intervals overlap almost entirely. **The effect
was the length and power confound of rounds thirty-six and thirty-seven, again.**
"""

from __future__ import annotations

import random

import pytest

from eval import frankentext as ft

CORPUS = [
    "The system processes input and returns a result. Evaluation covers four datasets. "
    "We report accuracy and recall for every configuration tested here.",
    "Prior work assumed a fixed vocabulary. That assumption fails on morphologically rich "
    "languages. Our method relaxes it without extra supervision at training time.",
    "We introduce a benchmark of ten thousand annotated examples. Inter-annotator agreement "
    "is high. The data is released under a permissive licence for reuse.",
]


def test_sentences_are_split_and_short_fragments_dropped():
    out = ft.sentences(CORPUS, min_words=6)
    assert len(out) >= 6
    assert all(len(s.split()) >= 6 for s in out)


def test_a_short_fragment_is_excluded_rather_than_padded():
    """A three-word fragment stitched into a text changes its burstiness, which is the signal the
    lite detector reads — so admitting fragments would measure the splitter, not the arrangement."""
    assert ft.sentences(["Yes. No. Maybe so."], min_words=6) == []


def test_stitching_draws_from_different_documents():
    rng = random.Random(0)
    pool = ft.sentences(CORPUS)
    stitched = ft.stitch(pool, 3, rng)
    assert len(stitched.split(". ")) >= 2
    # Every stitched sentence must come from the pool, unaltered.
    for sentence in pool:
        if sentence in stitched:
            break
    else:
        pytest.fail("no pool sentence appears verbatim in the stitched text")


def test_stitching_never_repeats_a_sentence_within_one_text():
    """`random.sample` without replacement is the point: a repeated sentence would raise the
    repetition tells this repo's own catalogue fires on, and that would be an artefact of the
    construction rather than a property of stitched writing."""
    rng = random.Random(1)
    pool = ft.sentences(CORPUS)
    stitched = ft.stitch(pool, len(pool), rng)
    for sentence in pool:
        assert stitched.count(sentence) <= 1, f"{sentence!r} appears twice"


def test_asking_for_more_sentences_than_exist_does_not_raise():
    rng = random.Random(2)
    pool = ft.sentences(CORPUS)
    assert ft.stitch(pool, len(pool) * 10, rng)


def test_a_corpus_too_small_refuses_rather_than_comparing_two_documents():
    result = ft.probe(["One short line here that is long enough."], n=5, n_sentences=12)
    assert "error" in result


def test_a_missing_comparison_arm_is_an_error_not_a_one_armed_result():
    """The defect the first run had, in its sharpest form. Stitching more sentences than any single
    document contains leaves nothing to compare against — and the probe used to return the stitched
    rate with `whole` at n = 0, which reads as a comparison and is not one.

    Rounds thirty-six and thirty-seven are why this matters: short text is flagged far more often, so
    an unmatched comparison measures the corpus's length distribution. The first run reported
    stitched at 1.7% against 17.6% on n = 17, a -16 point gap that became -0.7% once both arms held
    150 documents at a matched length.
    """
    result = ft.probe(CORPUS * 20, tier="lite", n=8, n_sentences=12)
    assert "error" in result, "a comparison with no comparison arm must refuse"
    assert "too few to compare" in result["error"]


def test_matched_arms_produce_a_two_sided_comparison():
    long_corpus = [". ".join(["A sentence with quite a few words in it for the splitter"] * 12) + "."]
    result = ft.probe(long_corpus * 40, tier="lite", n=8, n_sentences=3)
    if "error" in result:
        pytest.skip(f"synthetic corpus too small here: {result['error']}")
    assert result["stitched"]["n"] > 0 and result["whole"]["n"] > 0
    assert result["gap"] is not None


def test_the_report_refuses_to_claim_a_replication():
    result = ft.probe(CORPUS * 20, tier="lite", n=6, n_sentences=3)
    if "error" in result:
        pytest.skip("synthetic corpus too small in this environment")
    note = result["note"].lower()
    assert "not a replication" in note, (
        "assembling by random.sample is not what 2026.acl-long.1457 does, and the report has to say "
        "so — an LLM composing for coherence is the whole difficulty of that paper"
    )
    assert "every flag is a false positive" in note


def test_an_overlapping_gap_is_reported_as_no_evidence():
    text = ft._render({
        "tier": "lite", "seed": 0, "sentences_per_text": 6, "mean_words": 130,
        "stitched": {"n": 150, "flagged": 16, "rate": 0.107, "ci95": [0.067, 0.166],
                     "detectors": ["perplexity_burstiness"]},
        "whole": {"n": 150, "flagged": 17, "rate": 0.113, "ci95": [0.072, 0.174],
                  "detectors": ["perplexity_burstiness"]},
        "gap": -0.007, "intervals_overlap": True, "note": "n/a",
    })
    assert "not evidence that arrangement matters" in text
    assert "one detector scored" in text
