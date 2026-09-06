"""Rounds 114 and 120 wrote down a hypothesis and refused to assert it. This tests it.

Both rounds found that false-positive rate RISES with distance from a norm in function-word space
(z=+3.91 against the machine centroid, z=+6.55 against the corpus norm), and both wrote the same
tempting next step and declined it:

    non-native writers sit far out in function-word space — article and preposition use is exactly
    that signal — which would make the L2 false-positive result an instance of this effect. That is
    a hypothesis, not a result: there is no non-native corpus here.

There is one. The Pratama corpus carries a self-declared author status on every row — 36 Native and
36 Non-Native, balanced, mean 183 words — and is fetched from raw.githubusercontent.com, which is
reachable where huggingface.co is not.

MEASURED, function-word vocabulary 50, permutation test:

    arm              Non-Native Δ   Native Δ    diff      p        median words
    all documents         0.7749     0.7355   +0.0394   0.098      176 vs 180
    length-matched        0.7809     0.7369   +0.0441   0.066      175 vs 179

**Directionally right, not significant.** The gap points the way the hypothesis predicts in both
arms, and neither reaches 0.05 at n=36 per group — settling it needs ~79-104 per group. Length is
NOT the confound this time, which is worth stating because length faked this exact study once
already: the medians differ by four words.

These tests are about the instrument, not the answer. A hypothesis test that could only ever return
"supported" is the thing this file exists to prevent.
"""

from __future__ import annotations

from eval import native_distance as N


def test_the_permutation_test_finds_a_planted_difference() -> None:
    """Floor check: an instrument that cannot detect a real gap cannot report a null."""
    a = [1.0 + i * 0.01 for i in range(40)]
    b = [2.0 + i * 0.01 for i in range(40)]
    result = N.permutation_test(a, b, rounds=2000)
    assert result["p"] < 0.01 and result["observed"] < 0


def test_the_permutation_test_reports_a_null_when_the_groups_are_one_population() -> None:
    values = [0.5 + (i % 7) * 0.01 for i in range(80)]
    result = N.permutation_test(values[:40], values[40:], rounds=2000)
    assert result["p"] > 0.2, result


def test_a_p_value_of_exactly_zero_is_never_reported() -> None:
    """(hits + 1) / (rounds + 1). A zero p is not a p-value — it says "no shuffle beat it in the
    ones we tried", and the smallest honest claim at N permutations is 1/(N+1)."""
    a = [0.0] * 30
    b = [100.0] * 30
    result = N.permutation_test(a, b, rounds=500)
    assert result["p"] > 0, "a permutation p must never be exactly zero"
    assert result["p"] <= 2 / 501


def test_length_matching_pairs_on_word_count_and_drops_what_it_cannot_pair() -> None:
    """The control that matters: length faked this exact study once, in round 114, where the crude
    curve was significant in the WRONG direction purely because distant documents were shorter."""
    rows = (
        [{"status": "Non-Native", "words": w, "delta": 0.8} for w in (100, 200, 900)]
        + [{"status": "Native", "words": w, "delta": 0.7} for w in (105, 195)]
    )
    matched = N._matched(rows, "words")
    words = sorted(r["words"] for r in matched)
    assert 900 not in words, "an unpairable outlier must be dropped, not stretched to a partner"
    assert len(matched) == 4, matched
    # Each control is used once, or a single native document would anchor every pair.
    natives = [r for r in matched if r["status"] == "Native"]
    assert len({r["words"] for r in natives}) == len(natives)


def test_the_power_figure_turns_the_null_into_a_specification() -> None:
    """"Under-powered" is a word; the number behind it is what makes a null useful."""
    a = [0.80 + (i % 5) * 0.01 for i in range(30)]
    b = [0.76 + (i % 5) * 0.01 for i in range(30)]
    power = N.required_n(a, b)
    assert power["n_per_group"] and power["n_per_group"] > 0
    assert power["cohens_d"] and power["cohens_d"] > 0
    # A larger separation must need fewer documents, or the figure is not measuring what it claims.
    wider = N.required_n([x + 0.5 for x in a], b)
    assert wider["n_per_group"] < power["n_per_group"]


def test_no_difference_is_reported_as_unpowerable_rather_than_as_infinity() -> None:
    values = [0.5 + (i % 3) * 0.01 for i in range(30)]
    power = N.required_n(values, list(values))
    assert power["n_per_group"] is None and power["cohens_d"] == 0.0


def test_an_unscored_document_never_counts_as_a_clean_one() -> None:
    """The eighth-site trap, guarded here too: `score_text` returns max 0.0 with scored False, and
    0.0 below a threshold reads as 'not flagged' — a clean bill of health for a document nothing
    measured."""
    import inspect

    source = inspect.getsource(N.measure)
    assert 'result.get("scored") is not False' in source or 'scored") is False' in source, (
        "measure() must consult `scored` before treating a max as a real number"
    )
