"""The loop told users their drafts "scored worse" when nothing had been scored.

`_nothing_adopted_warning` already knew this trap. Its `vetoed >= rewrites` branch says so
outright: the meaning gate `continue`s BEFORE scoring, so "every draft scored worse" would
describe a comparison that did not happen, and the remedy differs -- more draws of a rewriter
that keeps changing the meaning is not the answer.

The sentinel-integrity check is the sibling rejection path, five lines further up the same loop,
and it `continue`s before scoring too. It was never counted. So a run in which every draft
mangled a locked span arrived at the function as `vetoed=0` and fell through to the final branch:

    _nothing_adopted_warning(rewrites=3, adopted=0, changed=False, vetoed=0)
    -> "...every draft scored worse than your text..."

MEASURED, and wrong twice over. Nothing was scored, and the advice it gives -- "try --best-of 3
for more draws" -- is the worst available answer: a rewriter that drops citations will drop them
again on every draw. The user is told to spend more compute on a failure that cannot resolve.

The counters are what make the message honest, so the tests assert on both the counting and the
arithmetic in the mixed case, where the three groups have to add up.
"""

from __future__ import annotations

from untell.scripts.run import _nothing_adopted_warning

LOCKED_SPAN_MARK = "altered a locked span"
SCORED_WORSE_MARK = "scored worse"


def test_drafts_refused_before_scoring_are_not_described_as_having_scored_worse():
    """The defect, as the call that exposed it."""
    warning = _nothing_adopted_warning(
        rewrites=3, adopted=0, changed=False, vetoed=0, sentinel_failed=3
    )

    assert warning is not None
    assert LOCKED_SPAN_MARK in warning, warning
    assert "None of them was scored" in warning, warning
    assert SCORED_WORSE_MARK not in warning, (
        f"claimed a score comparison that never ran: {warning}"
    )


def test_the_remedy_offered_is_one_that_can_actually_work():
    """"Try more draws" is the wrong advice here, and being wrong costs the user compute."""
    warning = _nothing_adopted_warning(
        rewrites=4, adopted=0, changed=False, vetoed=0, sentinel_failed=4
    )

    assert "different --rewriter" in warning
    assert "--best-of" not in warning, (
        f"suggested more draws for a failure that repeats on every draw: {warning}"
    )


def test_a_mixed_run_attributes_each_draft_to_the_gate_that_refused_it():
    """Three groups, and only the last was ever scored -- so the counts have to add up."""
    warning = _nothing_adopted_warning(
        rewrites=6, adopted=0, changed=False, vetoed=2, sentinel_failed=3
    )

    assert "3 altered a locked span" in warning, warning
    assert "2 changed the meaning" in warning, warning
    assert "1 scored worse" in warning, warning  # 6 - 2 - 3
    assert "Only the last group was ever scored" in warning


def test_the_meaning_gate_branch_is_unchanged_when_no_span_was_altered():
    """The existing behaviour has to survive: this branch was already correct."""
    warning = _nothing_adopted_warning(
        rewrites=3, adopted=0, changed=False, vetoed=3, sentinel_failed=0
    )

    assert "meaning gate refused every one" in warning
    assert LOCKED_SPAN_MARK not in warning


def test_the_plain_scored_worse_case_still_says_scored_worse():
    """The message that was over-applied is still right for the case it was written for.

    If this stopped firing, the fix would have replaced one wrong message with another.
    """
    warning = _nothing_adopted_warning(
        rewrites=2, adopted=0, changed=False, vetoed=0, sentinel_failed=0
    )

    assert SCORED_WORSE_MARK in warning
    assert LOCKED_SPAN_MARK not in warning


def test_a_run_that_adopted_something_says_nothing_at_all():
    """A warning that fires when the loop worked is noise on every successful run."""
    assert _nothing_adopted_warning(
        rewrites=3, adopted=1, changed=True, vetoed=0, sentinel_failed=2
    ) is None


def test_the_loop_counts_sentinel_rejections_at_the_point_it_refuses_them():
    """Guard the wiring, not just the message.

    The message can be perfect and still never appear if the counter is not incremented where the
    loop actually rejects. This asserts the increment sits with the `continue` that refuses a
    mangled span, which is the line that was missing it.
    """
    import inspect

    from untell.scripts import run as run_mod

    src = inspect.getsource(run_mod)
    marker = "sentinel_failed += 1\n                continue  # dropped/altered/DUPLICATED"
    assert marker in src, "the sentinel rejection no longer increments the counter beside it"
    assert src.count("sentinel_failed = 0") == 1, "the counter must be initialised exactly once"
