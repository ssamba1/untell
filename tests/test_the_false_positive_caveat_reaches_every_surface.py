"""A caveat in a dict nobody prints is the same as no caveat.

The false-positive note added for `score_text` says what a flagged verdict is worth — measured, 5 of
30 genuine HC3 human answers flagged at tier=full, two at 0.9922 and 0.9862. It is the sentence that
stands between "99.2% AI" and a person who wrote the text themselves.

Being on the result is not the same as arriving. VERIFIED on a flagged human answer at tier=full,
where the loop could not clear it:

    score_text result          carries it
    untell_text result         carries it
    untell-score terminal      prints it
    untell humanize terminal   prints it    (in a Warning panel)
    REST /score                carries it
    REST /humanize             carries it, and on `pre` as well

All six. **No defect.**

**The contract is narrower than it first looks, and getting that wrong is what these tests found.**
A first version asserted the note reaches the loop result on any flagged input, and it failed at the
lite tier — correctly. The loop merges the caveat from the score it REPORTS, which is `post`. On that
run `pre` was flagged at 0.7429 and `post` came back at 0.3772, cleared: there is no flagged verdict
left to qualify, so the note is properly absent. It survived at the full tier only because the
document stayed flagged.

So the caveat follows the VERDICT, not the input — and the tests below say that, rather than the
stronger thing that happened to be true on one tier.
"""

from __future__ import annotations

import contextlib
import io
import logging

import pytest

from untell.scripts.score import score_text

CAVEAT = "not proof of AI authorship"

# Formulaic enough that the lite tier flags it, which is all this file needs — the note is about what
# a flag is WORTH, and does not depend on the text really being AI.
FLAGGED = (
    "Moreover, the framework leverages a robust and comprehensive approach to delivery. "
    "Furthermore, it is important to note that this underscores the transformative impact. "
    "In conclusion, organizations must harness these seamless and pivotal solutions today."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def scored():
    result = score_text(FLAGGED, tier="lite", threshold=0.3)
    if not result.get("flagged"):
        pytest.skip("this text is not flagged on the installed tier")
    return result


def test_the_library_result_carries_it(scored) -> None:
    assert CAVEAT in (scored.get("warning") or "")


def test_the_score_cli_prints_it(scored) -> None:
    import untell.scripts.score as mod

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        mod.main([FLAGGED, "--tier", "lite"])
    assert CAVEAT in buffer.getvalue()


def test_the_loop_carries_it_exactly_when_its_verdict_is_flagged(scored) -> None:
    """The real contract. The loop reports `post`, so the caveat belongs to `post`'s verdict — and
    a run that CLEARS the text has no flagged verdict left to qualify."""
    from untell.scripts.run import untell_text

    result = untell_text(
        FLAGGED, tier="lite", threshold=0.3, max_iters=1, rewriter="structural", best_of=1
    )
    still_flagged = bool((result.get("post") or {}).get("flagged"))
    assert (CAVEAT in (result.get("warning") or "")) == still_flagged


def test_the_input_verdict_keeps_its_own_caveat(scored) -> None:
    """And the note is not lost — `pre` carries it, so a caller reporting the BEFORE verdict has the
    qualification beside the number it qualifies."""
    from untell.scripts.run import untell_text

    result = untell_text(
        FLAGGED, tier="lite", threshold=0.3, max_iters=1, rewriter="structural", best_of=1
    )
    pre = result.get("pre") or {}
    assert pre.get("flagged"), "premise: the input must be flagged"
    assert CAVEAT in (pre.get("warning") or "")


def test_the_humanize_cli_prints_it_when_the_verdict_stands(scored) -> None:
    """The surface that matters most: someone pasting their own writing into a humanizer. Asserted
    against the verdict actually reached, for the reason above."""
    import untell.scripts.run as mod
    from untell.scripts.run import untell_text

    result = untell_text(
        FLAGGED, tier="lite", threshold=0.3, max_iters=1, rewriter="structural", best_of=1
    )
    if not (result.get("post") or {}).get("flagged"):
        pytest.skip("the loop cleared this text on the installed tier; no verdict to qualify")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        mod.main([FLAGGED, "--tier", "lite", "--max-iters", "1",
                  "--rewriter", "structural", "--best-of", "1"])
    assert CAVEAT in buffer.getvalue()


def test_both_rest_endpoints_carry_it(scored) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from untell.api_server import app

    client = TestClient(app)
    score = client.post("/score", json={"text": FLAGGED, "tier": "lite"}).json()
    assert CAVEAT in str(score.get("warning"))
    loop = client.post(
        "/humanize",
        json={"text": FLAGGED, "tier": "lite", "rewriter": "structural",
              "max_iters": 1, "best_of": 1},
    ).json()
    # Same contract as the library: the caveat belongs to the verdict being reported, and `pre`
    # keeps its own either way.
    still_flagged = bool((loop.get("pre") or {}).get("flagged"))
    assert not still_flagged or CAVEAT in str((loop.get("pre") or {}).get("warning"))


def test_an_unflagged_verdict_carries_nothing_anywhere() -> None:
    """Guards the guard on every surface at once. A note that arrives regardless of the verdict is
    noise, and would make each assertion above pass without proving propagation."""
    plain = (
        "I drove up on Friday and the traffic was awful past the junction near the bridge. "
        "Took nearly four hours for what should have been two, which is about typical now."
    )
    result = score_text(plain, tier="lite", threshold=0.3)
    if result.get("flagged"):
        pytest.skip("the control text is flagged on this tier; it cannot show the difference")
    assert CAVEAT not in (result.get("warning") or "")
