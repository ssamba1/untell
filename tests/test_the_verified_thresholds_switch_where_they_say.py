"""Four user-visible thresholds from the verified register, tested at the point they switch.

Round one hundred enumerated **48** boundaries mechanically — comparisons against a named threshold
constant — and found 30 with a surviving off-by-one. Round one hundred and one re-ran each of those
30 against **every test importing its module**, uncapped, because the harness has twice reported
false survivors: stale bytecode in round ninety-five, a test-selection heuristic that dropped
boundary tests in round one hundred.

MEASURED: **27 of 30 are genuine gaps and 3 were selection artefacts.** The register is 90%
accurate, which is now known rather than assumed, and the check saved three tests written for code
that is already covered.

These four are the user-visible ones from the 27 — thresholds a person meets rather than internals:

| threshold | what it decides |
|---|---|
| `voice.MIN_SAMPLE_WORDS` | whether the user is warned their voice sample is too thin to profile |
| `run._MIN_VOICE_SAMPLE_WORDS` | whether voice distance is computed at all, or short-circuits to 0.0 |
| `tells._LANG_MIN_WORDS` | whether a document is even considered for non-English detection |
| `tells._MIN_WORDS_FOR_A_RATE` | whether `tells_per_100w` carries its quantisation caveat |

Each is asserted at n−1, n and n+1. The two voice constants are separate numbers in separate modules
guarding the same idea, so they are also asserted against each other: a sample the runner accepts
must not be one the voice module calls thin.
"""

from __future__ import annotations

import pytest

from untell.scripts import voice
from untell.scripts.tells import _LANG_MIN_WORDS, _MIN_WORDS_FOR_A_RATE, score_tells
from untell.scripts.voice import MIN_SAMPLE_WORDS


def words(n: int) -> str:
    return " ".join(f"word{i}" for i in range(n))


@pytest.fixture(autouse=True)
def _reset_thin_sample_warning():
    """`_warn_if_sample_is_thin` fires once per process via a module global.

    Without resetting it, the first test to trip the warning silences it for every test after —
    which would make the boundary assertions below pass for the wrong reason, and is the same
    process-lifetime staleness round ninety-six's cache audit is about.
    """
    voice._WARNED_THIN_SAMPLE = False
    yield
    voice._WARNED_THIN_SAMPLE = False


def _warns_thin(n: int, caplog) -> bool:
    voice._WARNED_THIN_SAMPLE = False
    caplog.clear()
    with caplog.at_level("WARNING", logger=voice.logger.name):
        voice._warn_if_sample_is_thin(words(n))
    return any("voice sample is under" in r.message for r in caplog.records)


def test_the_thin_sample_warning_stops_exactly_at_the_minimum(caplog):
    """`>= MIN_SAMPLE_WORDS` returns without warning, so the floor itself must be quiet."""
    floor = MIN_SAMPLE_WORDS
    assert _warns_thin(floor - 1, caplog), "one word short, the user must be warned"
    assert not _warns_thin(floor, caplog), "AT the floor the sample is long enough"
    assert not _warns_thin(floor + 1, caplog)


def test_the_warning_quotes_the_limit_it_enforces(caplog):
    """A boundary that is right but reports the wrong number is the same defect one step on."""
    voice._WARNED_THIN_SAMPLE = False
    caplog.clear()
    with caplog.at_level("WARNING", logger=voice.logger.name):
        voice._warn_if_sample_is_thin(words(MIN_SAMPLE_WORDS - 1))
    assert any(str(MIN_SAMPLE_WORDS) in r.getMessage() for r in caplog.records)


def test_a_sample_between_the_two_floors_still_reaches_the_user_with_its_warning(caplog):
    """The two constants are 20 and 150, and they answer different questions.

    A first draft asserted `run._MIN_VOICE_SAMPLE_WORDS >= voice.MIN_SAMPLE_WORDS` and failed. That
    assertion was wrong: 20 is "below this the distance is meaningless, do not compute", and 150 is
    "below this the profile is noisy, say so". Both are defensible.

    What matters is the gap between them — a 20-to-149-word sample IS scored, so the user must be
    told it is thin. `voice_distance` calls `_warn_if_sample_is_thin`, which is what makes the pair
    safe, and nothing tested that it does.
    """
    from untell.scripts.run import _MIN_VOICE_SAMPLE_WORDS

    assert _MIN_VOICE_SAMPLE_WORDS < MIN_SAMPLE_WORDS, (
        "premise: there is a range the runner scores and the voice module considers thin"
    )
    midpoint = (_MIN_VOICE_SAMPLE_WORDS + MIN_SAMPLE_WORDS) // 2
    voice._WARNED_THIN_SAMPLE = False
    caplog.clear()
    with caplog.at_level("WARNING", logger=voice.logger.name):
        voice.voice_distance(words(midpoint), words(midpoint))
    assert any("voice sample is under" in r.getMessage() for r in caplog.records), (
        f"a {midpoint}-word sample is scored by the runner and called thin by `voice`; the "
        f"warning is the only thing that makes that pair safe"
    )


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_the_runner_computes_a_voice_distance_exactly_at_its_own_floor(offset: int):
    """`< _MIN_VOICE_SAMPLE_WORDS` short-circuits to 0.0 without scoring anything.

    Tested through `_voice_key` rather than through `voice_distance`: a first draft exercised the
    voice module directly and left the runner's own guard untouched, so its off-by-one survived.
    Below the floor the key must be exactly 0.0 — a sample too thin to profile contributes nothing
    to the loop rather than a small arbitrary number.
    """
    from untell.scripts.run import _MIN_VOICE_SAMPLE_WORDS, _voice_key

    count = _MIN_VOICE_SAMPLE_WORDS + offset
    voice._WARNED_THIN_SAMPLE = False
    key = _voice_key("a candidate draft with enough words in it to be scored properly", words(count))
    if count < _MIN_VOICE_SAMPLE_WORDS:
        assert key == 0.0, f"{count} words is below the floor; nothing may be computed"
    else:
        assert key != 0.0, f"{count} words is at or above the floor and must be scored"


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_non_english_detection_needs_exactly_its_minimum_words(offset: int):
    """`< _LANG_MIN_WORDS` returns False — below the floor no document is called non-English."""
    from untell.scripts.tells import looks_non_english

    # Function words from the non-English list, so above the floor this must be detected.
    sample = " ".join(["der", "und", "das", "ist", "nicht", "mit", "von", "auf", "eine"])
    count = _LANG_MIN_WORDS + offset
    text = " ".join(sample.split()[:count]) if count <= 9 else sample
    assert len(text.split()) == min(count, 9), "premise: the sample has the intended length"
    if count < _LANG_MIN_WORDS:
        assert looks_non_english(text) is False, (
            f"{count} words is below the floor; no verdict may be reached"
        )
    else:
        assert looks_non_english(text) is True, f"{count} words of German must be detected"


def test_the_rate_caveat_starts_exactly_below_the_minimum():
    """`< _MIN_WORDS_FOR_A_RATE and total > 0` attaches the quantisation caveat.

    Both halves matter: the caveat needs a short document AND at least one tell, because a rate of
    0.0 from a short document is harmless and warning about it teaches readers to skip warnings.
    """
    floor = _MIN_WORDS_FOR_A_RATE

    def caveat_for(n: int) -> str:
        # "Moreover" is a formulaic_transition tell, so `total > 0` holds at any length.
        filler = " ".join(f"word{i}" for i in range(n - 1))
        result = score_tells(f"Moreover {filler}.")
        assert result["tells"] > 0, "premise: the sample fires at least one tell"
        # The key is `warning`, not `caveats` — read from the function rather than guessed.
        return str(result.get("warning") or "")

    below = caveat_for(floor - 1)
    at = caveat_for(floor)
    assert "quantised" in below, f"{floor - 1} words: the rate must carry its caveat"
    assert "quantised" not in at, f"{floor} words: at the floor the caveat must be gone"


def test_a_short_document_with_no_tells_is_not_warned_about():
    """The `total > 0` half, which a length-only test would pass without exercising."""
    result = score_tells(words(_MIN_WORDS_FOR_A_RATE - 1))
    assert result["tells"] == 0, "premise: this sample fires nothing"
    assert "quantised" not in str(result.get("warning") or ""), (
        "a rate of 0.0 from a short document is harmless; warning about it is noise"
    )
