"""Properties that must hold for any input, checked across module boundaries.

These are the assertions that do not belong to one module's test file because they are about how
the pieces compose: scrubbing twice must equal scrubbing once, locking then restoring must return
the original bytes, a text must be perfectly similar to itself. Each is the kind of property that
breaks silently — nothing raises, a number is just quietly wrong — and each is cheap enough to run
over every awkward input at once.

All of these passed when first written. That is worth saying plainly: this file is regression
protection, not a bug report. It exists because the session that added it found real defects in
`scrub_hidden` (49 invisible codepoints surviving) and in both meaning gates (truncation), and
those were found by probing properties rather than by testing behaviour case by case.
"""

from __future__ import annotations

import pytest

from untell.attacks import count_hidden, scrub_hidden
from untell.scripts.preserve import lock, restore
from untell.scripts.quality import similarity
from untell.scripts.tells import score_tells

TEXTS = [
    pytest.param("The trial enrolled 240 patients over 18 months at three sites.", id="facts"),
    pytest.param("Moreover, the framework leverages a robust approach — delivering.", id="tells"),
    pytest.param("See https://example.org/a?b=1 and Smith et al. (2019) for details.", id="urls"),
    pytest.param(
        "Emoji \U0001F468‍\U0001F469 and RTL ‏مرحبا and a soft­hyphen inside.",
        id="unicode",
    ),
    pytest.param("", id="empty"),
    pytest.param("   \n\t ", id="whitespace"),
    pytest.param("A", id="single-char"),
    pytest.param("word " * 400, id="long"),
]


@pytest.mark.parametrize("text", TEXTS)
def test_scrubbing_is_idempotent(text):
    """A second scrub must find nothing to do. If it does, the first pass left a carrier behind or
    the pass itself introduces one."""
    once = scrub_hidden(text)
    assert scrub_hidden(once) == once


@pytest.mark.parametrize("text", TEXTS)
def test_scrubbed_text_reports_no_hidden_characters(text):
    """The scrubber and the counter must agree. They are separate implementations of the same
    question, and a disagreement means one of them is wrong — which is exactly how 49 invisible
    codepoints came to survive the scrub while being reported clean."""
    assert count_hidden(scrub_hidden(text)) == 0


@pytest.mark.parametrize("text", TEXTS)
def test_lock_then_restore_returns_the_original_exactly(text):
    """Preserve-lock replaces facts with sentinels and puts them back. Round-tripping to anything
    other than the input byte-for-byte means a fact was altered or a sentinel leaked."""
    masked, spans = lock(text)
    assert restore(masked, spans) == text


@pytest.mark.parametrize("text", TEXTS)
def test_a_text_is_perfectly_similar_to_itself(text):
    """The meaning gate's floor case. This is also the assertion that catches a chunking bug: with
    aligned chunks, identical input must still align to itself."""
    assert similarity(text, text) == pytest.approx(1.0)


@pytest.mark.parametrize("text", TEXTS)
def test_tell_counts_are_never_negative(text):
    result = score_tells(text)
    assert result["tells"] >= 0
    assert result["tells_per_100w"] >= 0
    assert sum(result["by_category"].values()) <= result["tells"] or result["by_category"] == {}


@pytest.mark.parametrize("text", TEXTS)
def test_scrubbing_never_lengthens_the_visible_text(text):
    """Scrubbing removes carriers and normalises exotic spaces to U+0020. Neither adds characters,
    so a longer result means something was inserted rather than cleaned."""
    assert len(scrub_hidden(text)) <= len(text)


def test_the_input_list_is_not_empty():
    """Guards the guard: a parametrise list that silently became empty passes every test above."""
    assert len(TEXTS) >= 6
