"""On a saturating corpus the tell count is the only thing that moves, and nothing reported it.

MEASURED on 4 HC3 documents at full tier: P(AI) max gained +0.0000 on 4 of 4 — three of five
detectors saturate there, with or without `mage` — while tells fell 4->0, 1->0 and 1->0. The
result carried the flat number and not the fall, so a user on real AI text saw

    P(AI) max   1.00 -> 1.00   delta 0

and would reasonably conclude the run had done nothing, when the machine-writing markers the
catalogue exists to find had been removed.

`_saturated_max_caveat` already warns about that case in prose. This puts the numbers on the
result, so a JSON, MCP or REST caller reads a figure rather than parsing a sentence — and adds the
row to the table a CLI user actually looks at.

The repository already treats tells as a first-class signal: `untell tells` is a command, the loop
uses them to break ties between candidates inside the detector noise band, and `humanness` is
built from them. Every surface reported them except the one that does the rewriting.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from untell.scripts.run import _tells_delta, untell_text

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "Furthermore, it significantly improves overall efficiency and accuracy across the corpus."
)


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def test_the_result_carries_both_counts():
    result = untell_text(AI, tier="lite", threshold=0.30, max_iters=2, rewriter="composite", seed=3)

    assert isinstance(result.get("tells_before"), int), result.keys()
    assert isinstance(result.get("tells_after"), int), result.keys()


def test_the_counts_describe_the_texts_that_were_scored():
    """Before is the input, after is what came back — not two scores of the same string."""
    from untell.scripts.tells import score_tells

    result = untell_text(AI, tier="lite", threshold=0.30, max_iters=2, rewriter="composite", seed=3)

    assert result["tells_before"] == score_tells(AI)["tells"]
    assert result["tells_after"] == score_tells(result["final"])["tells"]


def test_a_broken_counter_returns_no_keys_rather_than_zeros(monkeypatch):
    """Zeros would read as "no tells", which is a claim. Absence is not."""
    import untell.scripts.tells as tells_module

    def _boom(*_a, **_k):
        raise RuntimeError("counter is broken")

    monkeypatch.setattr(tells_module, "score_tells", _boom)
    assert _tells_delta(AI, AI) == {}


def test_the_table_shows_the_row():
    """The CLI surface, where a flat P(AI) row is the whole story a user sees."""
    pytest.importorskip("rich")
    from untell.rich_output import print_humanize_result

    score = {"max": 1.0, "mean": 0.9, "detectors": {"d": 1.0}, "threshold": 0.30,
             "flagged": True, "verdict_threshold": 0.30, "tier": "full"}

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        print_humanize_result(
            "original text here, long enough to render properly",
            "rewritten text here, long enough to render properly",
            score, score, 2, "max_iters", tells_before=4, tells_after=0,
        )
    output = buffer.getvalue()

    assert "AI tells" in output, output
    assert "-4" in output, "the delta is the point of the row"


def test_the_row_is_absent_when_the_caller_has_no_counts():
    """Rendering must not invent numbers it was not given."""
    pytest.importorskip("rich")
    from untell.rich_output import print_humanize_result

    score = {"max": 0.5, "mean": 0.4, "detectors": {"d": 0.5}, "threshold": 0.30,
             "flagged": True, "verdict_threshold": 0.30, "tier": "lite"}

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        print_humanize_result("original text here", "rewritten text here", score, score, 1, "passed")

    assert "AI tells" not in buffer.getvalue()
