"""A saturated detector reports "no change" on text that changed, so the report has to say so.

MEASURED through the pipeline at the full tier, on the selector fix one result earlier: 4 documents
rewritten, tells/100w 3.80 -> 2.98, similarity 0.971 — and `max` sat at **0.9997 before and after**.
The Delta column printed "—". A 22% cut in tell density, reported as nothing happening.

That is not a rounding artefact. Over 80 corpus texts the ensemble max reaches >=0.999 on 100% of
HC3 AI text and 30% of RAID's, against 0% of human text. The member doing it is `hc3_roberta`, at
>=0.99 on 58 of 60 sentences of that genre; `roberta_openai` manages 2 of 60 (mean 0.7405) and drops
0.9986 -> 0.6228 under rewriting, so it is the one detector that does yield. The attribution sat in
five places before it was measured. `composite` and `targeted` both rank candidates on `(max, mean)`
for exactly this reason; the surface that reports the outcome was still showing the max alone.

The mean is already in both score dicts. Withholding it leaves the reader with the one number that
provably could not see what happened.
"""

from __future__ import annotations

import logging

import pytest

from untell.rich_output import _SATURATED_MAX, print_humanize_result

ORIGINAL = "It is worth noting that this pivotal approach leverages a robust framework."
FINAL = "This approach uses a solid framework."


def _score(mx: float, mean: float) -> dict:
    return {"max": mx, "mean": mean, "tier": "full", "flagged": mx >= 0.45}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_a_pinned_max_is_called_out(capsys) -> None:
    print_humanize_result(
        ORIGINAL, FINAL, _score(0.9997, 0.8100), _score(0.9997, 0.6200), 2, "exhausted"
    )
    out = capsys.readouterr().out
    assert "pinned" in out
    assert "0.8100" in out and "0.6200" in out


def test_an_unpinned_max_says_nothing_extra(capsys) -> None:
    """Guards the guard. The note must not appear on a run where the delta is informative, or it
    becomes noise the reader learns to skip."""
    print_humanize_result(
        ORIGINAL, FINAL, _score(0.8200, 0.7000), _score(0.3100, 0.2900), 2, "passed"
    )
    assert "pinned" not in capsys.readouterr().out


def test_one_side_pinned_is_not_enough(capsys) -> None:
    """A run that STARTED pinned and came down is the success case, and its delta is real. The note
    is about a comparison that cannot move, which needs both ends against the ceiling."""
    print_humanize_result(
        ORIGINAL, FINAL, _score(0.9997, 0.8100), _score(0.4000, 0.3500), 2, "passed"
    )
    assert "pinned" not in capsys.readouterr().out


def test_the_note_survives_a_score_dict_with_no_mean(capsys) -> None:
    """`mean` is optional in the wild — a stubbed or partial score dict is a real caller shape, and
    the saturation itself is still worth reporting without it."""
    print_humanize_result(
        ORIGINAL, FINAL, {"max": 0.9997, "tier": "full"}, {"max": 0.9997, "tier": "full"}, 1, "x"
    )
    out = capsys.readouterr().out
    assert "pinned" in out


def test_the_caveat_reaches_a_json_caller_too() -> None:
    """Surface parity. The CLI prints the note; a JSON, MCP or REST caller reads only the result
    dict's `warning`, and `pre`/`post` there are identical to four decimals on text that improved.
    Composed with the other caveats rather than replacing them — a run can carry a scrub payload, a
    scoring caveat and a pinned max at once."""
    from untell.scripts.run import _merge_warnings, _saturated_max_caveat

    caveat = _saturated_max_caveat(_score(0.9997, 0.8100), _score(0.9997, 0.6200))
    assert caveat and "pinned" in caveat and "0.6200" in caveat
    assert _saturated_max_caveat(_score(0.8200, 0.70), _score(0.3100, 0.29)) is None

    merged = _merge_warnings("text carried hidden characters", caveat)
    assert "hidden characters" in merged and "pinned" in merged


def test_both_surfaces_use_the_same_bar() -> None:
    """Two constants drifting apart is the failure this repo keeps finding. Same value, and the CLI
    note and the result-dict caveat must agree on when to appear."""
    from untell.scripts.run import _SATURATED_MAX as run_bar

    assert run_bar == _SATURATED_MAX


def test_the_bar_sits_above_every_human_reading() -> None:
    """0.99 is chosen so a detector pinned just below the rounding edge is caught, while the human
    side of both corpora — which never exceeded 0.4 in the measurement — cannot reach it."""
    assert 0.9 < _SATURATED_MAX < 0.999
