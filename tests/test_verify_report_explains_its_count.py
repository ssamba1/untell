"""The verify table printed two rows above "0/1 checkers passed".

`local:max (lite)` is an aggregate of the local detectors, not an independent checker, and it is
excluded from `n_configured` deliberately — the comment beside that list records the bug it fixed:
"two of five passing were reported as 2/5 checkers passed, and a run with one local detector read as
1/2". The count is right.

What a reader could not tell is WHICH of the two rows is not a checker. `configured` lists both
names, `n_configured` says one, and the rendered table gave no way to reconcile them — the same
reader-facing gap as the detector audit printing INVERTED four lines above "every detector responds
in the correct direction".
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.verify import _render as render
from untell.scripts.verify import verify

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_aggregate_row_is_marked() -> None:
    out = render(verify(AI, tier="lite", threshold=0.30))
    aggregate = [ln for ln in out.splitlines() if "local:max" in ln]
    assert aggregate, "premise: the aggregate row must still be shown — it is what the loop drives"
    assert "not counted" in aggregate[0], aggregate[0]


def test_a_real_checker_row_is_not_marked() -> None:
    """Guards the guard. Marking every row would satisfy the test above and explain nothing."""
    out = render(verify(AI, tier="lite", threshold=0.30))
    real = [ln for ln in out.splitlines() if "local:perplexity" in ln]
    assert real, "premise: at least one real checker must run"
    assert "not counted" not in real[0], real[0]


def test_the_marked_rows_reconcile_the_denominator() -> None:
    """The invariant: rows shown, minus rows marked as aggregates, equals the number the summary
    line divides by."""
    result = verify(AI, tier="lite", threshold=0.30)
    out = render(result)
    rows = [ln for ln in out.splitlines() if ln.startswith("  local:") or ln.startswith("  api:")]
    marked = [ln for ln in rows if "not counted" in ln]
    assert len(rows) - len(marked) == result["n_configured"], out


def test_the_verdict_is_unchanged_by_the_marking(monkeypatch: pytest.MonkeyPatch) -> None:
    """`passes_all` is computed over every row including the aggregate, and must stay that way —
    the max is below threshold exactly when every local detector is, so it cannot disagree.

    Pin the stdlib detector path. `tier="lite"` silently upgrades to GPT-2 whenever torch is
    importable, and the two disagree about this fixture: stdlib scores it 0.6848 (fails, which is
    what this test asserts) while the torch path scores 0.2824 and correctly PASSES. The product is
    right on both; the test was reading an unpinned configuration and failed on any machine with
    torch installed. Third occurrence of this trap in this suite — see the same note in
    tests/test_run.py and tests/test_layout_protects_every_rewriter.py.

    The premise is asserted rather than assumed, so a future drift in either scoring path fails on
    the premise line and names the number that moved.
    """
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    result = verify(AI, tier="lite", threshold=0.30)
    max_row = next(v for k, v in result["results"].items() if k.startswith("local:max"))
    assert max_row["ai"] >= 0.30, (
        f"premise: the fixture must be flagged for this test to mean anything (got {max_row['ai']})"
    )
    assert result["passes_all"] is False
    assert result["n_passing"] == 0
    assert "FAILS" in render(result)
