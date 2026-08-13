"""`best_of=0` drew a draft anyway, and `max_iters=0` returned the text with nothing said.

FOUND by asking what Result 202's finding implies in reverse. REST refuses an out-of-range value at
the schema edge, which is stronger than a caveat — so every constraint REST enforces is a claim about
valid input that the library does not make. Extracting them:

    max_iters   Ge1, Le100        best_of   Ge1, Le32
    threshold   Ge0.0, Le1.0      margin    Ge0.0, Le1.0
    text        MaxLen 50000      tier      Literal

MEASURED against the library, one paragraph at `tier=lite`:

    max_iters=1  best_of=1    changed=True   iters=1  rewrites=1  adopted=1
    max_iters=0               changed=False  iters=0  rewrites=0  adopted=0   nothing said
    max_iters=-3              changed=False  iters=0  rewrites=0  adopted=0   nothing said
    best_of=0                 changed=True   iters=1  rewrites=1  adopted=1   value ignored
    best_of=-2                changed=True   iters=1  rewrites=1  adopted=1   value ignored

**Two different failures.** A non-positive `max_iters` returns the input untouched and says nothing —
`_nothing_adopted_warning` cannot cover it, because no draft was drawn to refuse. A non-positive
`best_of` is not respected at all: the caller asked for zero drafts and got a rewrite, which is the
worse of the two, because the result looks like an ordinary successful run.

Warn rather than refuse, matching how this library already treats an unknown tier, an unknown style
and an unreachable threshold. REST keeps its 422, and Result 202 recorded why both are honest.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.run import _inert_budget_warning, untell_text

TEXT = (
    "Moreover, the framework leverages a robust approach to delivery at scale. "
    "Furthermore, it is important to note that this underscores the pivotal integration."
)
KWARGS = dict(tier="lite", threshold=0.3, rewriter="structural", seed=1)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("max_iters", [0, -3])
def test_no_iterations_says_the_loop_never_ran(max_iters: int) -> None:
    note = _inert_budget_warning(max_iters, 1) or ""
    assert "no rewriting was attempted" in note
    assert str(max_iters) in note, "the caller's own value has to appear, or they cannot find it"


@pytest.mark.parametrize("best_of", [0, -2])
def test_a_non_positive_draw_count_says_it_was_ignored(best_of: int) -> None:
    """The worse of the two: the run looks entirely normal, so nothing prompts the reader to check
    what they passed."""
    note = _inert_budget_warning(1, best_of) or ""
    assert "was ignored" in note and "one draft was drawn" in note


def test_both_can_fire_together() -> None:
    note = _inert_budget_warning(0, 0) or ""
    assert "no rewriting was attempted" in note and "was ignored" in note


@pytest.mark.parametrize("max_iters,best_of", [(1, 1), (2, 3), (100, 32)])
def test_ordinary_settings_say_nothing(max_iters: int, best_of: int) -> None:
    """Guards the guard. A note on every run is a note nobody reads."""
    assert _inert_budget_warning(max_iters, best_of) is None


def test_the_note_says_what_to_pass_instead() -> None:
    """A caveat naming a bad value without naming a good one leaves the reader guessing."""
    assert "Pass 1 or more" in (_inert_budget_warning(0, 0) or "")


def test_it_reaches_a_real_run() -> None:
    zero_iters = untell_text(TEXT, max_iters=0, best_of=1, **KWARGS)
    assert "no rewriting was attempted" in (zero_iters.get("warning") or "")
    assert zero_iters.get("changed") is False

    zero_draws = untell_text(TEXT, max_iters=1, best_of=0, **KWARGS)
    assert "was ignored" in (zero_draws.get("warning") or "")


def test_an_ordinary_run_stays_clean() -> None:
    result = untell_text(TEXT, max_iters=1, best_of=1, **KWARGS)
    warning = result.get("warning") or ""
    assert "no rewriting was attempted" not in warning
    assert "was ignored" not in warning


def test_rest_still_refuses_what_the_library_warns_about() -> None:
    """The two surfaces answer differently on purpose, and Result 202 recorded why: a schema that
    can refuse is stronger than a caveat, and the library warns because an embedding caller may be
    passing a value from a newer version. This pins that they have not silently converged."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from untell.api_server import app

    client = fastapi_testclient.TestClient(app)
    response = client.post(
        "/humanize", json={"text": TEXT, "tier": "lite", "max_iters": 0, "best_of": 1}
    )
    assert response.status_code == 422, response.text
