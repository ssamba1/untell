"""`--kinds boundary --workers 1` accepted the flag, ignored it, and swept every operator.

FOUND by running an experiment the sweep itself suggested. Round 110 argued that
`untell/scripts/audit.py` is classified unmeasurable because four workers contend for four cores,
and predicted that `--workers 1` would classify it measurable every time. Running that:

    python -m eval.mutation --all --kinds boundary --workers 1 --json
    03:58:35 -> 10:58:43   killed at a 7-hour timeout, no output

The 4-worker boundary sweep of the same tree takes about 50 minutes. The serial run was not 4x
slower; it was a different job. The CLI dispatches on worker count:

    runner = run_parallel if args.workers > 1 else run
    kwargs = {"workers": args.workers, "kinds": kinds} if args.workers > 1 else {}

`kinds` rode along in the parallel-only branch, and `run` had no such parameter to receive it. So
the serial path swept every operator kind — the 1,397-candidate run `run_parallel`'s own docstring
puts at about four hours — for a caller who asked for the 340-mutant one. Nothing warned. In a run
that finished, the only evidence would have been a `by_kind` map carrying more keys than the flag
named, and nobody reads that to check a filter they passed.

Two smaller divergences came from the same place: `_worker` skips a module the filter emptied,
`run` did not and paid a full baseline pass — up to the whole timeout — for each one; and the
filter must run BEFORE `limit_per_file`, because spacing a sample then filtering it selects
different mutants from filtering then spacing.

The general defect is a flag whose meaning depends on an unrelated flag's value. This file pins the
two runners to the same selection rather than trusting that the next parameter added to one gets
added to the other.
"""

from __future__ import annotations

import inspect

from eval import mutation


def test_both_runners_accept_the_kinds_filter() -> None:
    assert "kinds" in inspect.signature(mutation.run).parameters
    assert "kinds" in inspect.signature(mutation.run_parallel).parameters


def test_the_cli_hands_kinds_to_whichever_runner_it_picks() -> None:
    """The dispatch itself, read from source: `kinds` must not sit inside a branch keyed on
    `workers`. Asserting on the signature alone would have passed while the CLI still dropped it."""
    src = inspect.getsource(mutation.main) if hasattr(mutation, "main") else ""
    if not src:
        import pathlib
        src = pathlib.Path(mutation.__file__).read_text(encoding="utf-8")
    marker = 'kwargs = {"kinds": kinds}'
    assert marker in src, "kinds must be passed unconditionally, not only when workers > 1"
    assert '{"workers": args.workers, "kinds": kinds} if args.workers > 1' not in src


def test_both_runners_narrow_the_same_way_in_the_same_order() -> None:
    """The two selections, read from the functions themselves.

    An earlier version of this test reproduced each runner's narrowing INSIDE the test and asserted
    the two reproductions agreed. It passed against the unfixed code — because it never touched the
    code. It proved that filter-then-cap differs from cap-then-filter, which is a fact about lists,
    not about `eval/mutation.py`. That is the vacuity this whole module exists to hunt, written by
    hand into its own test file, and it was caught by running the test against the pre-fix tree
    rather than by reading it.

    So: assert on the real bodies. Both must apply the `kinds` filter, and in both it must come
    before the `limit`/`limit_per_file` spacing, because the order changes which mutants a capped
    run measures.
    """
    for fn in (mutation.run, mutation._worker):
        body = inspect.getsource(fn)
        assert "if kinds:" in body, f"{fn.__name__} does not apply the kinds filter"
        filt = body.index("if kinds:")
        caps = [body.index(m) for m in ("if limit_per_file:", "if limit:") if m in body]
        assert caps, f"{fn.__name__} has no cap block to order against"
        assert filt < min(caps), (
            f"{fn.__name__} caps before it filters; spacing then filtering selects different "
            "mutants from filtering then spacing"
        )


def test_a_module_the_filter_empties_is_skipped_not_baselined() -> None:
    """`_worker` skipped these; `run` paid a full baseline pass for each. The baseline is the
    expensive call — up to the entire timeout — so the waste is per emptied module, not per mutant."""
    body = inspect.getsource(mutation.run)
    assert "if not candidates:" in body, (
        "run() has no empty-candidate skip, so a module the filter emptied still pays a baseline"
    )
    assert body.index("if not candidates:") < body.index("baseline = _failures("), (
        "the empty-candidate skip must come before the baseline pass, or it saves nothing"
    )
