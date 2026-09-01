"""An advisory caveat was 88% of the request it qualified.

PROFILED on a 50,000-character `score_text` call — the REST path's own `_MAX_INPUT_CHARS` cap —
`_mostly_locked_warning` was **87.8% of the total on ordinary prose** and **91.8%** on a
comma-separated blob: 3.4s and 12.6s of spaCy NER for a sentence of advice. The scoring path locks
for no other reason; rewriting locks separately and none of this touches it.

The note is a threshold on a *proportion*, and a proportion is the one quantity you can estimate from
a sample. So long input is read for 5,000 characters and re-read in full only when that estimate
lands near the bar. MEASURED on 40 long documents built from real pre-LLM abstracts, the prefix
estimates the full share to within 0.0261 at worst against a margin of 0.15, with zero verdict flips.

What this file pins is that the shortcut did not change the answer, and — the case that actually
distinguishes it — that the fallback is real: a document whose prefix says one thing and whose full
text says another must get the full text's answer.
"""

from __future__ import annotations

import time

import pytest

import untell.scripts.score as score

QUOTED = '"' + ("Alpha beta gamma delta epsilon zeta eta theta iota. " * 2) + '" '
PLAIN = "The system runs and then it stops and then it runs once more. "


def _exact(text: str) -> str | None:
    """What the note was before round sixty-four: always the whole document."""
    share = score._locked_share(text)
    if share is None:
        return None
    return score._MOSTLY_LOCKED_NOTE if share > score._LOCKED_SHARE_BAR else None


def test_a_document_whose_prefix_disagrees_with_its_tail_gets_the_tails_answer():
    """The discriminating case. Every other test here passes with the fallback deleted.

    The first 5,000 characters sit just under the bar; the rest is heavily quoted, so the true share
    is well over it. Answering from the prefix alone gives the wrong verdict, and the margin exists
    precisely so that this document is re-read.
    """
    head = ""
    while len(head) < score._LOCK_NOTE_PREFIX_CHARS + 200:
        head += QUOTED + PLAIN + PLAIN
    document = head + (QUOTED * 3 + PLAIN) * 40

    prefix_share = score._locked_share(document[: score._LOCK_NOTE_PREFIX_CHARS])
    full_share = score._locked_share(document)
    assert prefix_share is not None and full_share is not None
    assert prefix_share < score._LOCKED_SHARE_BAR < full_share, (
        f"the fixture stopped straddling the bar: prefix {prefix_share:.3f}, full {full_share:.3f}")
    assert abs(prefix_share - score._LOCKED_SHARE_BAR) <= score._LOCK_NOTE_MARGIN, (
        "the fixture no longer lands inside the margin, so it stopped testing the fallback")

    assert score._mostly_locked_warning(document) == score._MOSTLY_LOCKED_NOTE


def test_a_thoroughly_locked_document_still_gets_the_note():
    document = (('"' + "The quick brown fox jumped over the lazy dog near Paris in 1998. " * 3
                 + '" ') + "Also. ") * 120
    assert len(document) > score._LOCK_NOTE_PREFIX_CHARS
    assert score._mostly_locked_warning(document) == score._MOSTLY_LOCKED_NOTE
    assert score._mostly_locked_warning(document) == _exact(document)


def test_ordinary_long_prose_still_gets_no_note():
    document = ("The system processes each record and stores the result. " * 400)[:30_000]
    assert score._mostly_locked_warning(document) is None
    assert score._mostly_locked_warning(document) == _exact(document)


def test_short_input_is_measured_exactly_rather_than_estimated():
    """No behaviour change at all below the prefix size, which is where most documents live."""
    for document in ("", "Short.", PLAIN * 5, QUOTED * 3):
        assert len(document) <= score._LOCK_NOTE_PREFIX_CHARS
        assert score._mostly_locked_warning(document) == _exact(document)


def test_the_margin_is_far_wider_than_the_measured_estimation_error():
    """0.15 against a worst observed 0.0261. If someone narrows the margin toward the error, the
    shortcut starts answering from a sample in cases where the sample cannot decide."""
    worst_measured_error = 0.0261
    assert score._LOCK_NOTE_MARGIN > 5 * worst_measured_error


def test_the_note_is_never_allowed_to_break_the_score_it_qualifies():
    """The original contract, kept through the rewrite: a caveat that raises is no caveat."""
    assert score._locked_share(None) is None  # type: ignore[arg-type]
    assert score._mostly_locked_warning("") is None


def _capped(shape: str, seed: int) -> str:
    """50,000 characters, unique per call so the score and NER caches both miss."""
    if shape == "prose":
        return (f"Report {seed}. The system processes data efficiently. " * 1400)[:50_000]
    return (f"z{seed}," + "a," * 25_000)[:50_000]


@pytest.mark.parametrize("shape,ceiling", [("prose", 1.0), ("commas", 6.0)])
def test_a_capped_request_does_not_spend_seconds_on_a_caveat(shape, ceiling):
    """The finding, as a bound rather than a story — and measured warm, which is the correction
    round sixty-five made to round sixty-four.

    A cold process pays a one-time ~1.0s spaCy model load. Timing the first call folds that constant
    into the result and makes a ceiling far looser than it looks: the original 6.0s bound needed a
    26x regression on prose before it fired, against the MEASURED 0.229s a warm call takes. So the
    first call is a warm-up and is not timed.

    Warm at `674d04f` (before the fix) against `7773aee` (after): prose 1.526s -> 0.229s and commas
    10.852s -> 1.498s. Each ceiling sits about four times the measured cost, because CI machines vary
    and this guards against a return of the old shape rather than benchmarking — and each is below
    the old cost, so both fail on the pre-fix code. VERIFIED by running this file in a worktree at
    `674d04f`: commas 11.46s against its 6.0s ceiling, prose 1.44s against its 1.0s one. An earlier
    draft used 3.0s for prose, which the old code passed; a ceiling the defect clears is decoration.
    """
    score.score_text(_capped(shape, 999), tier="lite")  # pay the model load, untimed

    start = time.perf_counter()
    score.score_text(_capped(shape, 1), tier="lite")
    elapsed = time.perf_counter() - start
    assert elapsed < ceiling, (
        f"{shape}: {elapsed:.2f}s warm to score 50,000 characters, ceiling {ceiling}s")
