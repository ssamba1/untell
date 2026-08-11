"""The opener pool was frequency-screened. The DOSE was not.

Every member of `_OPENERS` was chosen because humans measurably use it. But the transform then
applied one to a fraction of sentences set by `intensity * 0.6` — 0.42 at the default — against a
measured human share of 3.13%. Screening the vocabulary and then over-applying it by 12x leaves a
fingerprint made entirely of human-attested words.
"""

from __future__ import annotations

import random
import re

from untell.rewriter.structural import _OPENERS, _vary_openers

_POOL = re.compile(
    r"^(?:" + "|".join(re.escape(o.rstrip(",")) for o in _OPENERS) + r")\b[,\s]", re.I
)

# 20 sentences that all open the same way: the worst case for `repeated_sentence_openers`, and
# the input this transform exists to improve.
_REPETITIVE = [f"The system handles case number {i} without any difficulty at all." for i in range(20)]


def _share(sentences: list[str]) -> float:
    return sum(1 for s in sentences if _POOL.match(s)) / len(sentences)


def test_the_output_share_tracks_the_requested_rate_not_every_sentence():
    """`rate` is a budget share. At 0.10 about a tenth of sentences may carry a pool opener."""
    random.seed(20260811)
    shares = [_share(_vary_openers(list(_REPETITIVE), rate=0.10)) for _ in range(30)]
    mean = sum(shares) / len(shares)
    assert 0.05 <= mean <= 0.16, f"mean share {mean:.3f} should sit near the requested 0.10"


def test_the_old_dose_would_fail_this():
    """Pins the regression. A per-sentence coin flip at 0.42 puts a marker on ~42% of sentences."""
    random.seed(20260811)
    shares = [_share(_vary_openers(list(_REPETITIVE), rate=0.42)) for _ in range(30)]
    mean = sum(shares) / len(shares)
    assert mean <= 0.50, "sanity: a 0.42 budget cannot exceed half the sentences"
    # And the human-band rate must be clearly separated from it.
    random.seed(20260811)
    human_band = sum(_share(_vary_openers(list(_REPETITIVE), rate=0.03)) for _ in range(30)) / 30
    assert human_band < mean / 3, f"0.03 gave {human_band:.3f}, 0.42 gave {mean:.3f}"


def test_a_zero_rate_inserts_nothing():
    random.seed(1)
    assert _vary_openers(list(_REPETITIVE), rate=0.0) == _REPETITIVE


def test_the_budget_still_prefers_the_sentences_that_repeat_an_opener():
    """The transform's actual job. With a small budget, spend it where openers collide."""
    random.seed(7)
    mixed = [
        "The system handles the first case without difficulty.",
        "The system handles the second case without difficulty.",
        "The system handles the third case without difficulty.",
        "Engineers reviewed the findings before the release went out.",
        "Nobody expected the throughput to double in a single quarter.",
    ]
    hit_repeated = 0
    for _ in range(40):
        out = _vary_openers(list(mixed), rate=0.20)
        changed = [i for i, (a, b) in enumerate(zip(mixed, out)) if a != b]
        if changed and all(i < 3 for i in changed):
            hit_repeated += 1
    assert hit_repeated >= 30, (
        f"only {hit_repeated}/40 budgets went to the repeated-opener sentences"
    )


def test_an_already_marked_sentence_is_not_double_marked():
    random.seed(3)
    marked = ["Basically, the system handles every case." for _ in range(10)]
    for _ in range(20):
        for s in _vary_openers(list(marked), rate=1.0):
            assert s.lower().count("basically") <= 1, s
