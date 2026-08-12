"""`repeats` exists to report a spread. It must not report zero because the spread was removed.

`measure_ceiling(repeats=N)` re-runs the whole corpus N times and publishes
`post_mean_max_stdev` and the per-run means, so a figure can be read with its uncertainty instead
of as a point estimate. The docstring quotes the reason: the same corpus moved a rewriter's mean
max P(AI) from 0.080 to 0.144 across two runs.

Seeding `untell_text` from its input text broke that. Every repeat became byte-identical —
MEASURED at repeats=3, means [0.2458, 0.2458, 0.2458], stdev 0.0 — and a stdev of zero does not
read as "the sampling was disabled", it reads as "this number has no uncertainty". That is worse
than the noise it replaced, because it is confidently wrong in the direction of overclaiming.

Fixed by seeding each repeat with its own run index, which keeps BOTH properties: repeat i differs
from repeat j, and repeat i is identical on every invocation. Before the seeding work only the
first held; before this fix only the second did.
"""
from __future__ import annotations

import pytest

from eval.ceiling import measure_ceiling


@pytest.fixture(scope="module")
def repeated() -> dict:
    import os

    os.environ["UNTELL_LITE_NO_TORCH"] = "1"
    return measure_ceiling(tier="lite", rewriter="composite", max_iters=1, best_of=1, repeats=3)


def test_the_repeats_are_not_all_the_same_run(repeated):
    means = repeated["run_post_means"]
    assert len(means) == 3
    assert len(set(means)) > 1, (
        f"three repeats produced the identical mean {means[0]} — `repeats` is re-running the same "
        "seeded draw, so the spread it reports is an artifact of that, not of the rewriter"
    )


def test_the_reported_spread_is_not_a_hardcoded_zero(repeated):
    assert repeated["post_mean_max_stdev"] > 0.0


def test_the_whole_measurement_still_reproduces():
    """The property the seeding was for. A spread that cannot be re-derived is not evidence."""
    import os

    os.environ["UNTELL_LITE_NO_TORCH"] = "1"
    kw = dict(tier="lite", rewriter="composite", max_iters=1, best_of=1, repeats=2)
    assert measure_ceiling(**kw)["run_post_means"] == measure_ceiling(**kw)["run_post_means"]


def test_a_single_pass_reports_no_spread(repeated):
    """One sample has no spread to report, and inventing one would be the opposite failure."""
    import os

    os.environ["UNTELL_LITE_NO_TORCH"] = "1"
    once = measure_ceiling(tier="lite", rewriter="composite", max_iters=1, best_of=1, repeats=1)
    assert len(once["run_post_means"]) == 1
    assert once.get("post_mean_max_stdev") in (0.0, None)
