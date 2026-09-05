"""A transient timeout permanently mislabelled a module, and nothing could tell it from a real one.

FOUND by chasing why `untell/scripts/audit.py` flipped between `unmeasured` and `unprotected`.
Round 110 blamed contention between the sweep's four workers and recorded that as the cause. Tested
directly, it is wrong. Every condition the sweep can present, timing that module's own selection:

    cold fresh worktree, no __pycache__      113s     <- what the sweep actually does
    four concurrent copies, four cores       177-180s <- the sweep's own worker count
    solo, warm working tree, under load      206s
    round 107's recorded figure              267s
    the cut                                  300s

Not one condition reaches the timeout, and the cold worktree — the sweep's real environment — is
the FASTEST of them. Yet a timeout was once observed. So the distribution has a tail that crosses
300s occasionally, and one crossing was enough to write the module off in a committed artefact:
round 110 moved the register's protected share 44.7% -> 43.8% on that single flip, and three rounds
went into chasing it.

`_failures` returned the same `UNUSABLE` for a timeout and for a run that died before reporting, so
the `unmeasurable` record could only say "times out **or** fails to collect". Two causes with
opposite remedies — one wants a bigger budget or another try, the other wants a dependency
installed — reported as one, which is the defect this module keeps finding in other people's code.

The fix splits the sentinel, retries ONCE on timeout only, and records which cause fired.
"""

from __future__ import annotations

from eval import mutation


def test_the_two_causes_have_different_sentinels() -> None:
    assert mutation.UNUSABLE != mutation.TIMED_OUT
    assert set(mutation.UNUSABLE_BASELINES) == {mutation.UNUSABLE, mutation.TIMED_OUT}


def test_a_timeout_is_retried_once_and_then_given_up_on(monkeypatch) -> None:
    calls = []

    def fake(tree, tests, timeout):
        calls.append(1)
        return mutation.TIMED_OUT

    monkeypatch.setattr(mutation, "_failures", fake)
    baseline, row = mutation._usable_baseline(mutation.REPO, ("t.py",), 300, "m.py")
    assert len(calls) == 2, f"expected exactly one retry, got {len(calls)} calls"
    assert baseline == mutation.TIMED_OUT
    assert row is not None and row["cause"] == "timeout" and row["retried"] is True
    assert "timed out twice" in row["why"]


def test_a_timeout_that_passes_on_the_retry_is_measured_not_written_off(monkeypatch) -> None:
    """The whole point. One unlucky crossing must not cost the module its measurement."""
    seq = iter([mutation.TIMED_OUT, 0])
    monkeypatch.setattr(mutation, "_failures", lambda *a: next(seq))
    baseline, row = mutation._usable_baseline(mutation.REPO, ("t.py",), 300, "m.py")
    assert baseline == 0
    assert row is None, "a module that answered on the retry must not be listed unmeasurable"


def test_a_collect_failure_is_not_retried(monkeypatch) -> None:
    """Deterministic: re-running buys an identical answer for the price of another full timeout."""
    calls = []
    monkeypatch.setattr(mutation, "_failures",
                        lambda *a: (calls.append(1), mutation.UNUSABLE)[1])
    baseline, row = mutation._usable_baseline(mutation.REPO, ("t.py",), 300, "m.py")
    assert len(calls) == 1, "a collect failure must not be retried"
    assert row["cause"] == "collect_error" and row["retried"] is False
    assert "exits without reporting a result" in row["why"]


def test_the_reason_says_which_cause_fired(monkeypatch) -> None:
    """It used to say "times out or fails to collect" because the caller could not tell. A reader
    needs to know whether to raise --timeout or install something."""
    monkeypatch.setattr(mutation, "_failures", lambda *a: mutation.TIMED_OUT)
    _, timed = mutation._usable_baseline(mutation.REPO, ("t.py",), 300, "m.py")
    monkeypatch.setattr(mutation, "_failures", lambda *a: mutation.UNUSABLE)
    _, dead = mutation._usable_baseline(mutation.REPO, ("t.py",), 300, "m.py")
    assert timed["why"] != dead["why"]
    for row in (timed, dead):
        assert " or " not in row["why"], f"still conflates two causes: {row['why']!r}"


def test_no_baseline_check_compares_against_one_sentinel_only() -> None:
    """The regression the split nearly introduced, guarded generally.

    `verify_survivors` tested `baseline == UNUSABLE`. After the split that misses TIMED_OUT — and
    the consequence is not a missed skip: -2 is a NUMBER, so `observed > baseline` holds for
    essentially any run, and every survivor of that module would have been reported "killed by the
    wider suite". A false-survivor rate reported better than it is, from a sentinel change two
    hundred lines away. Any future `== UNUSABLE` guard has the same hole.
    """
    import inspect
    src = inspect.getsource(mutation)
    code = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    assert "== UNUSABLE" not in code, (
        "a bare `== UNUSABLE` comparison misses TIMED_OUT; use `in UNUSABLE_BASELINES`"
    )


def test_a_timeout_still_counts_as_a_kill_when_scoring_a_mutant() -> None:
    """The sentinel split must not change what a timeout MEANS on the mutant side, where it is the
    suite noticing in the loudest way available."""
    import inspect
    src = inspect.getsource(mutation)
    assert src.count("in UNUSABLE_BASELINES or") >= 3, (
        "all three mutant-scoring sites must treat both sentinels as a kill"
    )
