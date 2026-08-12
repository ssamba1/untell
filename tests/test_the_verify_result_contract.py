"""`verify()`'s result shape, pinned — because reading it wrong fails silently.

Probing whether `untell verify` can disagree with `untell score`, the first run reported "0
disagreements" from `v.get("passed")`. There is no `passed` key; it is `passes_all`. Every lookup
returned None, no row matched either filter, and the answer came back clean and meaningless.

That is the failure this repository keeps finding in its own code — a check that cannot fire reads
exactly like a check that found nothing — and here it happened to a probe reading a public result
dict. Nothing pinned the key set, so a rename would leave every downstream reader silently vacuous
rather than raising.

The disagreement question itself: none found. Over 16 paired HC3 documents at lite tier, `verify`
and `score` agreed on every one — no text where verify passed and score flagged, none the other
way. Exit codes check out too, 1 on FAIL and 0 on PASS, once measured without a pipe in the way
(`$?` after `| tail` is tail's status, which briefly looked like exit 0 on a failing run).
"""
from __future__ import annotations

import pytest

from untell.scripts.verify import verify

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale "
    "and improves accuracy across the evaluated corpus substantially."
)
HUMAN = (
    "I went to the shop on the corner and it was closed for the day, so I walked home again "
    "feeling fairly annoyed about the whole business."
)

REQUIRED = {"configured", "n_configured", "n_passing", "passes_all", "results", "threshold"}


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


@pytest.mark.parametrize("text", [AI, HUMAN], ids=["ai", "human"])
def test_the_result_carries_every_documented_key(text: str):
    """A renamed key does not raise for a caller using .get() — it returns None forever."""
    result = verify(text, tier="lite")
    missing = REQUIRED - set(result)
    assert not missing, f"verify() no longer returns {sorted(missing)}; readers using .get() go quiet"


@pytest.mark.parametrize("text", [AI, HUMAN], ids=["ai", "human"])
def test_the_counts_agree_with_the_verdict(text: str):
    """`passes_all` must be derivable from the counts, or the summary can contradict its own table."""
    result = verify(text, tier="lite")
    n_configured, n_passing = result["n_configured"], result["n_passing"]

    assert n_passing <= n_configured
    assert result["passes_all"] is (n_configured > 0 and n_passing == n_configured), (
        f"passes_all={result['passes_all']} against {n_passing}/{n_configured} passing"
    )


def test_nothing_configured_is_not_a_pass():
    """The direction that matters for CI: zero checkers must never read as success."""
    result = verify(AI, tier="lite")
    if result["n_configured"] == 0:
        assert result["passes_all"] is False


def test_the_aggregate_row_is_not_counted_as_a_checker():
    """`results` carries an aggregate row that `n_configured` excludes, deliberately.

    Pinned because the two numbers look wrong together — a table of two rows above "0/1 checkers
    passed" — and the display already carries a "(aggregate, not counted)" marker to explain it.
    """
    result = verify(AI, tier="lite")
    aggregates = [name for name in result["results"] if name.startswith("local:max ")]
    assert len(result["results"]) == result["n_configured"] + len(aggregates)


def test_local_proxies_are_named_as_local():
    """With no commercial keys set, a reader must be able to tell what actually ran."""
    result = verify(AI, tier="lite")
    assert all(name.startswith("local:") for name in result["results"]), result["results"].keys()
